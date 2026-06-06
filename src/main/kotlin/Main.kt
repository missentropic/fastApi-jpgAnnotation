package org.example


import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.fasterxml.jackson.module.kotlin.readValue
import javafx.application.Application
import javafx.geometry.Pos
import javafx.scene.Scene
import javafx.scene.canvas.Canvas
import javafx.scene.canvas.GraphicsContext
import javafx.scene.control.Label
import javafx.scene.control.ListView
import javafx.scene.image.Image
import javafx.scene.image.ImageView
import javafx.scene.input.MouseButton
import javafx.scene.layout.BorderPane
import javafx.scene.layout.StackPane
import javafx.scene.paint.Color
import javafx.stage.Stage

import java.net.URI
import java.net.URL
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import java.nio.file.Path
import java.io.File
import java.io.ByteArrayInputStream
import javax.imageio.ImageIO
import javax.swing.JFrame
//import javax.swing.JPanel
import javax.swing.SwingUtilities
import kotlin.math.hypot
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import kotlin.math.atan2

data class BrowseItem(
    val name: String,
    val type: String,
    val path: String
)

data class BrowseResponse(
    val current_path: String,
    val items: List<BrowseItem>
)

data class PointDto(val x: Double, val y: Double)
{
    fun toArray(): List<Double> {
        return listOf(x, y)
    }

    operator fun plus(other: PointDto): PointDto {
            return PointDto(
                x + other.x,
                y + other.y
            )
        }
    operator fun PointDto.minus(other: PointDto) =
        PointDto(x - other.x, y - other.y)

    operator fun PointDto.times(scale: Double) =
        PointDto(x * scale, y * scale)
}






data class PolygonExport(
    val image_path: String,
    val closed: Boolean,
    val points: List<PointDto>
)



class FileBrowserFX : Application() {

    //}

    private val apiBase = "http://localhost:8000"
    private val client = HttpClient.newHttpClient()
    private val mapper = jacksonObjectMapper()

    private var currentPath = ""
    private var points = mutableListOf<PointDto>()
    private var centeredPoints = mutableListOf<PointDto>()
    private var pointsSorted = mutableListOf<PointDto>()
    private var polygon_closed = false
    private var select_top_left_corner=PointDto(0.0,0.0)

    private lateinit var imageView: ImageView
    private lateinit var canvas: Canvas
    //private var polygonClosed = false
    private val closeThresholdPx = 10.0
    private var currentImagePath: String = ""


    override fun start(stage: Stage) {
        val listView = ListView<String>()
        val pathLabel = Label("/")
        imageView = ImageView().apply {
        preserveRatioProperty().set(true)
        fitWidth = 900.0
        fitHeight = 700.0
    }

        canvas = Canvas(900.0, 700.0)

        val imagePane = StackPane(imageView, canvas)
        //imagePane.alignment = Pos.CENTER
        imagePane.alignment = Pos.TOP_LEFT

        val root = BorderPane()
        root.top = pathLabel
        root.left = listView
        root.center = imagePane


        fun load(path: String = "") {
            var loadpath=path

            println("CLICKED PATH RAW: ${path}")
            val encodedPath = URLEncoder.encode(path, StandardCharsets.UTF_8)

            //val url = "http://localhost:8000/download?path=" + encodedPath;
            //val uri = URI("$apiBase/browse?path=$path")
            val uri = URI("$apiBase/browse?path=$encodedPath")
            val request = HttpRequest.newBuilder(uri).GET().build()
            val response = client.send(request, HttpResponse.BodyHandlers.ofString())

            val browse = mapper.readValue<BrowseResponse>(response.body())
            currentPath = browse.current_path
            println("currentpath= $currentPath")
            pathLabel.text = "/$currentPath"

            listView.items.clear()

            if (currentPath.isNotEmpty()) listView.items.add("..")

            browse.items.forEach {
                listView.items.add(
                    if (it.type == "directory") "[${it.name}]" else it.name
                )
            }

            listView.setOnMouseClicked {
                val selected = listView.selectionModel.selectedItem ?: return@setOnMouseClicked

                if (selected == "..") {
                    println("go up directory")
                    val parent=currentPath.substringBeforeLast("/", "")
                    println("subsequent path:, $parent")
                    load(parent)
                    return@setOnMouseClicked
                }

                val clean = selected.removePrefix("[").removeSuffix("]")
                val item = browse.items.firstOrNull { it.name == clean } ?: return@setOnMouseClicked

                if (item.type == "directory") {
                    println("directory clicked is ${item.path}")
                    load(item.path)
                } else {
                    println("\nfilename for loadImage is ${item.path} and ${item.name}")
                    //File(path).toURI().toString()
                    //loadImage(item.path)
                    val encodedPath = URLEncoder.encode("${item.name}", StandardCharsets.UTF_8)
                    val uri = URI("http://localhost:8000/download?path=$encodedPath")

                    loadImage(File(item.path).toURI().toString())

                    //val downloadedImage: ByteArray=download(item.path, item.name)
                    val downloadedImage: ByteArray=download(encodedPath, encodedPath)
                    val image = Image(ByteArrayInputStream(downloadedImage))
                    imageView.image = image
                    //println("downloaded image: $downloadedImage")
                    //download(File(item.path).toURI().toString(), (item.name))
                }
            }
        }
        setupCanvasEvents()
        load()



        stage.title = "FastAPI File Browser"
        stage.scene = Scene(root, 1200.0, 800.0)
        stage.scene.setOnKeyPressed { e ->
            if (e.isControlDown && e.code.name == "S") {
                exportPolygon()
            }
        }

        stage.show()
    }
    // ================= Image Loading =================

    private fun loadImage(remotePath: String) {
        points.clear()
        polygon_closed = false
        currentImagePath = remotePath

        clearCanvas()

        //val uri = URI("$apiBase/download?path=$remotePath")
        val uri = URI("$remotePath")
        val image = Image(uri.toString(), false)
        println("\nfilename received in loadimage is $uri")
        imageView.image = image
    }
    // ================= Mouse Interaction =================

    private fun setupCanvasEvents() {
        canvas.setOnMouseClicked { e ->
            if (imageView.image == null) return@setOnMouseClicked

            val scale = calculateScale()
            val origin = calculateOffset()
            val ix = ((e.x )/ scale).toInt()
            val iy = ((e.y )/ scale).toInt()



            when (e.button) {
                MouseButton.PRIMARY -> {




                    if (!polygon_closed && points.size >= 3 && isNearFirst(e.x, e.y)) {
                        polygon_closed = true
                        exportPolygon()}
                    else if (!polygon_closed) {
                        //addPoint(ix, iy)
                        //addPoint(x=e.x, y=e.y)
                        addPoint(x=ix.toDouble(), y=iy.toDouble())

                        println("points, $points on scale $scale")

                    }
                    println("\nPolygon closed is  $polygon_closed nbr points is ${points.size}")

                }



                MouseButton.SECONDARY ->{
                    deleteNearest(e.x/scale, e.y/scale)
                    polygon_closed = false}

                else -> {
                    // ignore other buttons
                }
            }

            redraw()
        }
    }

    // ================= Drawing =================
    private fun isNearFirst(viewX: Double, viewY: Double): Boolean {
        if (points.isEmpty()) return false
        val scale = calculateScale()
        val first = select_top_left_corner
        //val first = points.first()
        val fx = first.x * scale
        val fy = first.y * scale

        val dx = fx - viewX
        val dy = fy - viewY
        return ((dx * dx) + (dy * dy)) <= closeThresholdPx * closeThresholdPx
    }
    private fun redraw() {
        clearCanvas()
        val gc = canvas.graphicsContext2D
        val scale = calculateScale()

        gc.stroke = Color.LIME
        gc.lineWidth = 2.0

        for (i in 0 until points.size - 1) {
            val p1 = points[i]
            val p2 = points[i + 1]
            gc.strokeLine(
                p1.x * scale, p1.y * scale,
                p2.x * scale, p2.y * scale
            )
        }
        if (polygon_closed && points.size >= 3) {
            val first = points.first()
            val last = points.last()
            gc.strokeLine(
                last.x * scale, last.y * scale,
                first.x * scale, first.y * scale
            )
        }
        gc.fill = Color.RED
        points.forEach {
            gc.fillOval(
                it.x * scale - 4,
                it.y * scale - 4,
                8.0, 8.0

            )
        }
        gc.fill = Color.BLUE

        gc.fillOval(select_top_left_corner.x *scale,select_top_left_corner.y*scale,8.0,8.0)


    }

    private fun download(remotePath: String, filename: String):ByteArray {
        val uri = URI("$apiBase/download?path=$remotePath")
        val request = HttpRequest.newBuilder(uri).GET().build()
        val response = client.send(request, HttpResponse.BodyHandlers.ofByteArray())

        val target = Path.of(System.getProperty("user.home"), "Downloads", filename)
        Files.write(target, response.body())

        println("Downloaded: $target")
        return response.body()
    }

    private fun exportPolygon() {
        if (points.size < 3) return

        val payload = PolygonExport(
            image_path = currentImagePath,
            closed = polygon_closed,
            points = points.toList()

        )

        val json = mapper.writeValueAsString(payload)

        val request = HttpRequest.newBuilder()
            .uri(URI("$apiBase/annotations"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build()

        client.sendAsync(request, HttpResponse.BodyHandlers.discarding())

        //println("Polygon exported for $currentImagePath")
    }



// ================= Logic =================
private fun addPoint(x: Double, y: Double) {
    //val scale = calculateScale()
    if (points.isEmpty()) {
        select_top_left_corner = PointDto(x, y )
    }
    //points.add(PointDto(x / scale, y / scale))
    //points.add(PointDto(x*scale , y*scale ))
    points.add(PointDto( x, y ))
    sortOnAngle()
}
/***private fun addPoint(x: Double, y: Double) {
        //val scale = calculateScale()
        points.add(PointDto(x , y ))
    }***/

private fun deleteNearest(x: Double, y: Double) {
    if (points.isEmpty())
    return

    // assume each point has attributes .x and .y
     /*       idx, _ = min(
    enumerate(points),
    key=lambda item: math.hypot(item[1].x - x, item[1].y - y)
    )

    points.pop(idx)*/
    println("point to delete , $x, $y from $points")
    val idx = points
        .mapIndexed { i, p ->
            //val v = imageToView(p, scale)
            i to hypot((p.x - x).toDouble(), (p.y - y).toDouble())
        }
        .minBy { it.second }
        .first

    points.removeAt(idx)

}



private fun calculateScale(): Double {
    val img = imageView.image ?: return 1.0
    val sx = imageView.fitWidth / img.width
    val sy = imageView.fitHeight / img.height
    //val shp=imageView.image.width
    //val origin = calculateOffset()
    println("img sizes width ${img.width}  height: ${img.height}, offset ")
    return minOf(sx, sy)
}

    private fun calculateOffset(): PointDto {

        val scale=calculateScale()
        val ox = ((imageView.fitWidth-scale*imageView.image.width)/2)
        val oy = ((imageView.fitHeight-scale*imageView.image.height)/2)
        print("offset origin $ox $oy")
        return PointDto(ox, oy)
    }


    private fun centerPoints() {
        if (points.size <= 1) {
            //centeredPoints = mutableListOf<PointDto>()
            return
        } else {
            val cx = points.sumOf { it.x.toDouble() } / points.size
            val cy = points.sumOf { it.y.toDouble() } / points.size

            println("cx and cy $cx $cy")

            println("RAW POINTS: ${points.map { Pair(it.x, it.y) }}")

            centeredPoints = points.map {
                PointDto(
                    (it.x - cx).toDouble(),
                    (it.y - cy).toDouble()
                )
            }.toMutableList()

            println("centroid coordinates $centeredPoints")
        }
    }

    fun sortOnAngle() {
        centerPoints()
        pointsSorted.clear()

        if (centeredPoints.size > 2) {

            // Calculate angles for each centered point
            val indexedAngles = centeredPoints.mapIndexed { index, p ->
                val angle = atan2(p.y, p.x)
                index to angle
            }

            // Sort indices by angle
            val sortedIndices = indexedAngles
                .sortedBy { it.second }
                .map { it.first }

            // Rebuild sorted list
            for (idx in sortedIndices) {
                pointsSorted.add(points[idx])
            }

            // Replace original list
            points = pointsSorted.toMutableList()
        }
    }


private fun clearCanvas() {
    canvas.graphicsContext2D.clearRect(
        0.0, 0.0, canvas.width, canvas.height
    )
}
/*private fun imageToView(p: PointDto, scale: Double): Point {
    return Point((p.x * scale).toInt(), (p.y * scale).toInt())
}*/
//private val points = mutableListOf<PointDto>()
/*class ImagePanel(private val imageUrl: String) : JPanel() {

    private val image: BufferedImage = ImageIO.read(URL(imageUrl))
    private val points = mutableListOf<PointDto>()

    init {
        preferredSize = Dimension(900, 700)

        addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                when (e.button) {
                    MouseEvent.BUTTON1 -> addPoint(e.x, e.y)
                    MouseEvent.BUTTON3 -> deleteNearest(e.x, e.y)
                }
                repaint()
            }
        })
    }

    // ================= Drawing =================
    override fun paintComponent(g: Graphics) {
        super.paintComponent(g)
        val g2 = g as Graphics2D

        g2.setRenderingHint(
            RenderingHints.KEY_ANTIALIASING,
            RenderingHints.VALUE_ANTIALIAS_ON
        )


        private fun calculateScale(): Double {
            val img = imageView.image ?: return 1.0
            val sx = imageView.fitWidth / img.width
            val sy = imageView.fitHeight / img.height
            return minOf(sx, sy)
        }

        val scale = calculateScale()
        val imgW = (image.width * scale).toInt()
        val imgH = (image.height * scale).toInt()

        g2.drawImage(image, 0, 0, imgW, imgH, null)

        // polygon lines
        if (points.size >= 2) {
            g2.color = Color.GREEN
            g2.stroke = BasicStroke(2f)

            for (i in 0 until points.size - 1) {
                val p1 = imageToView(points[i], scale)
                val p2 = imageToView(points[i + 1], scale)
                g2.drawLine(p1.x, p1.y, p2.x, p2.y)
            }
        }

        // points
        g2.color = Color.RED
        points.forEach {
            val p = imageToView(it, scale)
            g2.fillOval(p.x - 5, p.y - 5, 10, 10)
        }
    }*/


    }
fun main() {
    Application.launch(FileBrowserFX::class.java)
}


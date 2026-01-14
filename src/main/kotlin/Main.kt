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
import javax.imageio.ImageIO
import javax.swing.JFrame
//import javax.swing.JPanel
import javax.swing.SwingUtilities
import kotlin.math.hypot

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



class FileBrowserFX : Application() {

    //}

    private val apiBase = "http://localhost:8000"
    private val client = HttpClient.newHttpClient()
    private val mapper = jacksonObjectMapper()

    private var currentPath = ""
    private val points = mutableListOf<PointDto>()

    private lateinit var imageView: ImageView
    private lateinit var canvas: Canvas
    private var polygonClosed = false
    private val closeThresholdPx = 10.0

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
        imagePane.alignment = Pos.CENTER

        val root = BorderPane()
        root.top = pathLabel
        root.left = listView
        root.center = imagePane


        fun load(path: String = "") {
            val uri = URI("$apiBase/browse?path=$path")
            val request = HttpRequest.newBuilder(uri).GET().build()
            val response = client.send(request, HttpResponse.BodyHandlers.ofString())

            val browse = mapper.readValue<BrowseResponse>(response.body())
            currentPath = browse.current_path
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
                    load(currentPath.substringBeforeLast("/", ""))
                    return@setOnMouseClicked
                }

                val clean = selected.removePrefix("[").removeSuffix("]")
                val item = browse.items.firstOrNull { it.name == clean } ?: return@setOnMouseClicked

                if (item.type == "directory") {
                    load(item.path)
                } else {
                    loadImage(item.path)

                    download(item.path, item.name)
                }
            }
        }
        setupCanvasEvents()
        load()



        stage.title = "FastAPI File Browser"
        stage.scene = Scene(root, 1200.0, 800.0)
        stage.show()
    }
    // ================= Image Loading =================

    private fun loadImage(remotePath: String) {
        points.clear()
        polygonClosed = false
        clearCanvas()

        val uri = URI("$apiBase/download?path=$remotePath")
        val image = Image(uri.toString(), false)
        imageView.image = image
    }
    // ================= Mouse Interaction =================

    private fun setupCanvasEvents() {
        canvas.setOnMouseClicked { e ->
            if (imageView.image == null) return@setOnMouseClicked

            val scale = calculateScale()
            val ix = e.x / scale
            val iy = e.y / scale



            when (e.button) {
                MouseButton.PRIMARY -> {

                    if (!polygonClosed && points.size >= 3 && isNearFirst(e.x, e.y)) {
                        polygonClosed = true}
                    else if (!polygonClosed) {
                        addPoint(ix, iy)
                    }
                }



                MouseButton.SECONDARY ->{
                    deleteNearest(ix, iy)
                    polygonClosed = false}

                else -> {
                    // ignore other buttons
                }
            }
            /*when (e.button) {
                MouseButton.PRIMARY ->
                    points.add(PointDto(ix, iy))

                MouseButton.SECONDARY ->
                    deleteNearest(ix, iy)

                MouseButton.MIDDLE,
                MouseButton.BACK,
                MouseButton.FORWARD,
                MouseButton.NONE -> {
                    // ignore
                }
            }*/
            redraw()
        }
    }

    // ================= Drawing =================
    private fun isNearFirst(viewX: Double, viewY: Double): Boolean {
        if (points.isEmpty()) return false
        val scale = calculateScale()
        val first = points.first()
        val fx = first.x * scale
        val fy = first.y * scale

        val dx = fx - viewX
        val dy = fy - viewY
        return dx * dx + dy * dy <= closeThresholdPx * closeThresholdPx
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
        if (polygonClosed && points.size >= 3) {
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
    }

    private fun download(remotePath: String, filename: String) {
        val uri = URI("$apiBase/download?path=$remotePath")
        val request = HttpRequest.newBuilder(uri).GET().build()
        val response = client.send(request, HttpResponse.BodyHandlers.ofByteArray())

        val target = Path.of(System.getProperty("user.home"), "Downloads", filename)
        Files.write(target, response.body())

        println("Downloaded: $target")
        //return response.body()
    }


// ================= Logic =================

private fun addPoint(x: Double, y: Double) {
        //val scale = calculateScale()
        points.add(PointDto(x , y ))
    }

private fun deleteNearest(x: Double, y: Double) {
    if (points.isEmpty()) return
    //val scale = calculateScale()
    val idx = points
        .mapIndexed { i, p ->
            i to hypot(p.x - x, p.y - y)
        }
        .minBy { it.second }
        .first

    points.removeAt(idx)

}


private fun calculateScale(): Double {
    val img = imageView.image ?: return 1.0
    val sx = imageView.fitWidth / img.width
    val sy = imageView.fitHeight / img.height
    return minOf(sx, sy)
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


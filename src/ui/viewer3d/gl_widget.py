# src/ui/viewer3d/gl_widget.py
import numpy as np
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMatrix4x4, QVector3D
from PySide6.QtCore import Qt, QPoint
import OpenGL.GL as gl
from OpenGL.GL import shaders

class GLViewerWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 500)
        
        # Cámara Orbital
        self.camera_target = QVector3D(0.0, 1.0, 0.0)
        self.last_mouse_pos = QPoint()
        self.yaw = -0.5
        self.pitch = 0.2
        self.zoom = 3.5
        
        # Datos de la malla
        self.vertices = np.array([], dtype=np.float32)
        self.indices = np.array([], dtype=np.uint32)
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.index_count = 0

    def initializeGL(self):
        gl.glClearColor(0.11, 0.11, 0.13, 1.0) # Fondo oscuro idéntico a la imagen
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # Shaders con Iluminación Estructural (Efecto Metal/Tela)
        VERTEX_SHADER = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        uniform mat4 model;
        uniform mat4 view;
        uniform mat4 projection;
        out vec3 FragPos;
        void main() {
            FragPos = vec3(model * vec4(aPos, 1.0));
            gl_Position = projection * view * model * vec4(aPos, 1.0);
        }
        """

        FRAGMENT_SHADER = """
        #version 330 core
        in vec3 FragPos;
        out vec4 FragColor;
        void main() {
            // Simulación de iluminación de estudio para dar volumen al modelo
            vec3 normal = normalize(cross(dFdx(FragPos), dFdy(FragPos)));
            vec3 lightDir = normalize(vec3(1.0, 2.0, 1.0));
            float diff = max(dot(normal, lightDir), 0.0);
            
            vec3 ambient = vec3(0.25, 0.25, 0.27);
            vec3 diffuse = diff * vec3(0.55, 0.55, 0.58);
            
            // Color base gris acorazado
            vec3 baseColor = vec3(0.6, 0.6, 0.63);
            FragColor = vec4((ambient + diffuse) * baseColor, 1.0);
        }
        """
        self.shader = shaders.compileProgram(
            shaders.compileShader(VERTEX_SHADER, gl.GL_VERTEX_SHADER),
            shaders.compileShader(FRAGMENT_SHADER, gl.GL_FRAGMENT_SHADER)
        )
        self._create_grid()

    def _create_grid(self):
        """Genera la cuadrícula (grid) del suelo."""
        grid_verts = []
        size = 4.0
        steps = 20
        for i in range(-steps, steps + 1):
            val = (i / steps) * size
            grid_verts.extend([val, 0.0, -size,  val, 0.0, size])
            grid_verts.extend([-size, 0.0, val,  size, 0.0, val])
            
        self.grid_data = np.array(grid_verts, dtype=np.float32)
        self.grid_vao = gl.glGenVertexArrays(1)
        self.grid_vbo = gl.glGenBuffers(1)
        
        gl.glBindVertexArray(self.grid_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.grid_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, self.grid_data.nbytes, self.grid_data, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 3 * self.grid_data.itemsize, None)
        gl.glEnableVertexAttribArray(0)
        gl.glBindVertexArray(0)

    def load_mesh(self, vertices: np.ndarray, indices: np.ndarray):
        self.makeCurrent()
        self.vertices = vertices
        self.indices = indices
        self.index_count = len(indices)

        if self.vao is None:
            self.vao = gl.glGenVertexArrays(1)
            self.vbo = gl.glGenBuffers(1)
            self.ebo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self.indices.nbytes, self.indices, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 3 * self.vertices.itemsize, None)
        gl.glEnableVertexAttribArray(0)
        gl.glBindVertexArray(0)
        self.update()

    def paintGL(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        # Calcular Matrices de Cámara
        view = QMatrix4x4()
        cam_x = np.sin(self.yaw) * np.cos(self.pitch) * self.zoom
        cam_y = np.sin(self.pitch) * self.zoom
        cam_z = np.cos(self.yaw) * np.cos(self.pitch) * self.zoom
        view.lookAt(QVector3D(cam_x, cam_y + 1.0, cam_z), self.camera_target, QVector3D(0.0, 1.0, 0.0))
        model = QMatrix4x4()

        # 1. Dibujar el Suelo (Grid)
        gl.glUseProgram(self.shader)
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(self.shader, "projection"), 1, gl.GL_FALSE, self.projection.data())
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(self.shader, "view"), 1, gl.GL_FALSE, view.data())
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(self.shader, "model"), 1, gl.GL_FALSE, model.data())
        
        gl.glBindVertexArray(self.grid_vao)
        gl.glDrawArrays(gl.GL_LINES, 0, len(self.grid_data) // 3)
        
        # 2. Dibujar el Modelo de Armadura
        if self.index_count > 0:
            gl.glBindVertexArray(self.vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self.index_count, gl.GL_UNSIGNED_INT, None)
            gl.glBindVertexArray(0)

    def resizeGL(self, w: int, h: int):
        gl.glViewport(0, 0, w, h)
        self.projection = QMatrix4x4()
        self.projection.perspective(45.0, w / float(h if h > 0 else 1), 0.1, 100.0)

    def mousePressEvent(self, event): self.last_mouse_pos = event.position()
    def mouseMoveEvent(self, event):
        dx = event.position().x() - self.last_mouse_pos.x()
        dy = event.position().y() - self.last_mouse_pos.y()
        if event.buttons() & Qt.LeftButton:
            self.yaw -= dx * 0.01
            self.pitch = np.clip(self.pitch + dy * 0.01, -1.4, 1.4)
            self.update()
        self.last_mouse_pos = event.position()
    def wheelEvent(self, event):
        self.zoom = max(0.5, min(self.zoom - event.angleDelta().y() * 0.005, 15.0))
        self.update()
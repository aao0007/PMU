# src/ui/viewer3d/gl_widget.py
"""
Visor 3D OpenGL para modelos FLVER de Elden Ring.
Soporta: rotación orbital, zoom, wireframe, iluminación Phong con normales calculadas.
"""
import numpy as np
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMatrix4x4, QVector3D, QSurfaceFormat
from PySide6.QtCore import Qt, QPoint
import OpenGL.GL as gl
from OpenGL.GL import shaders

# ── GLSL Shaders ──────────────────────────────────────────────────────────────

_VERT_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform mat3 uNormalMatrix;

out vec3 vWorldPos;
out vec3 vNormal;

void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    vWorldPos = worldPos.xyz;
    vNormal   = uNormalMatrix * aNormal;
    gl_Position = uProjection * uView * worldPos;
}
"""

_FRAG_SRC = """
#version 330 core
in vec3 vWorldPos;
in vec3 vNormal;

out vec4 FragColor;

uniform vec3 uCamPos;
uniform bool uWireframe;
uniform vec3 uBaseColor;

void main() {
    if (uWireframe) {
        FragColor = vec4(0.2, 0.8, 1.0, 1.0);
        return;
    }

    vec3 N = normalize(vNormal);
    // dos luces: principal frontal, relleno trasero
    vec3 L1 = normalize(vec3(1.2, 2.0,  1.5));
    vec3 L2 = normalize(vec3(-0.6, 0.8, -1.0));

    float d1 = max(dot(N, L1), 0.0);
    float d2 = max(dot(N, L2), 0.0) * 0.25;

    // Specular Blinn-Phong
    vec3 V  = normalize(uCamPos - vWorldPos);
    vec3 H1 = normalize(L1 + V);
    float spec = pow(max(dot(N, H1), 0.0), 64.0) * 0.35;

    vec3 ambient  = uBaseColor * 0.18;
    vec3 diffuse  = uBaseColor * (d1 + d2);
    vec3 specular = vec3(spec);

    vec3 color = ambient + diffuse + specular;
    // tonemapping suave
    color = color / (color + vec3(0.8));
    FragColor = vec4(color, 1.0);
}
"""

_GRID_VERT = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uVP;
void main() { gl_Position = uVP * vec4(aPos, 1.0); }
"""

_GRID_FRAG = """
#version 330 core
out vec4 FragColor;
void main() { FragColor = vec4(0.28, 0.28, 0.30, 0.7); }
"""


# ── helper geometry ───────────────────────────────────────────────────────────

def _compute_normals(verts: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Computa normales por triángulo y promedia por vértice."""
    n_verts = len(verts)
    normals = np.zeros((n_verts, 3), dtype=np.float32)
    tri_indices = indices.reshape(-1, 3)
    v0 = verts[tri_indices[:, 0]]
    v1 = verts[tri_indices[:, 1]]
    v2 = verts[tri_indices[:, 2]]
    edge1 = v1 - v0
    edge2 = v2 - v0
    face_normals = np.cross(edge1, edge2)   # (N_tris, 3)
    # Acumular
    np.add.at(normals, tri_indices[:, 0], face_normals)
    np.add.at(normals, tri_indices[:, 1], face_normals)
    np.add.at(normals, tri_indices[:, 2], face_normals)
    # Normalizar
    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    lens = np.where(lens == 0, 1, lens)
    return (normals / lens).astype(np.float32)


def _make_grid(size: float = 3.0, divisions: int = 24) -> np.ndarray:
    lines = []
    step = size * 2 / divisions
    for i in range(divisions + 1):
        v = -size + i * step
        lines += [v, 0, -size,  v, 0, size]
        lines += [-size, 0, v,  size, 0, v]
    return np.array(lines, dtype=np.float32)


# ── widget ────────────────────────────────────────────────────────────────────

class GLViewerWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setSamples(4)          # MSAA 4x
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)
        super().__init__(parent)

        self.setMinimumSize(400, 400)

        # Cámara
        self._yaw   = 0.4
        self._pitch = 0.25
        self._zoom  = 3.0
        self._target = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self._last_pos = QPoint()

        # Estado mesh
        self._verts:   np.ndarray | None = None
        self._indices: np.ndarray | None = None
        self._n_indices = 0
        self._mesh_dirty = False

        # Opciones
        self.wireframe   = False
        self.show_grid   = True
        self.base_color  = np.array([0.62, 0.60, 0.58], dtype=np.float32)

        # GL handles
        self._shader = None
        self._grid_shader = None
        self._vao = self._vbo = self._nbo = self._ebo = None
        self._grid_vao = self._grid_vbo = None
        self._proj = QMatrix4x4()

        self.setFocusPolicy(Qt.StrongFocus)

    # ── public API ────────────────────────────────────────────────────────────

    def load_mesh(self, verts_flat: np.ndarray, indices: np.ndarray):
        """Recibe vértices [x,y,z,...] e índices y los sube a la GPU."""
        self._verts   = verts_flat.reshape(-1, 3).astype(np.float32)
        self._indices = indices.astype(np.uint32)
        self._n_indices = len(self._indices)
        self._mesh_dirty = True
        self.makeCurrent()
        self._upload_mesh()
        self.doneCurrent()
        self.update()

    def clear_mesh(self):
        self._verts = None
        self._indices = None
        self._n_indices = 0
        self._mesh_dirty = False
        self.update()

    def set_wireframe(self, on: bool):
        self.wireframe = on
        self.update()

    def set_base_color(self, r: float, g: float, b: float):
        self.base_color = np.array([r, g, b], dtype=np.float32)
        self.update()

    # ── GL lifecycle ──────────────────────────────────────────────────────────

    def initializeGL(self):
        gl.glClearColor(0.10, 0.10, 0.12, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(gl.GL_MULTISAMPLE)

        # Compilar shaders
        self._shader = shaders.compileProgram(
            shaders.compileShader(_VERT_SRC, gl.GL_VERTEX_SHADER),
            shaders.compileShader(_FRAG_SRC, gl.GL_FRAGMENT_SHADER),
        )
        self._grid_shader = shaders.compileProgram(
            shaders.compileShader(_GRID_VERT, gl.GL_VERTEX_SHADER),
            shaders.compileShader(_GRID_FRAG, gl.GL_FRAGMENT_SHADER),
        )

        # Reservar VAOs para el modelo
        self._vao = gl.glGenVertexArrays(1)
        self._vbo = gl.glGenBuffers(1)
        self._nbo = gl.glGenBuffers(1)
        self._ebo = gl.glGenBuffers(1)

        # Grid
        self._grid_vao = gl.glGenVertexArrays(1)
        self._grid_vbo = gl.glGenBuffers(1)
        grid_data = _make_grid()
        gl.glBindVertexArray(self._grid_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._grid_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, grid_data.nbytes, grid_data, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
        gl.glEnableVertexAttribArray(0)
        gl.glBindVertexArray(0)
        self._grid_n = len(grid_data) // 3

    def _upload_mesh(self):
        """Sube vértices + normales + índices a la GPU."""
        if self._verts is None or len(self._verts) == 0:
            return
        normals = _compute_normals(self._verts, self._indices)

        gl.glBindVertexArray(self._vao)

        # VBO posiciones
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, self._verts.nbytes, self._verts, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
        gl.glEnableVertexAttribArray(0)

        # NBO normales
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._nbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, normals.nbytes, normals, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
        gl.glEnableVertexAttribArray(1)

        # EBO índices
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, gl.GL_STATIC_DRAW)

        gl.glBindVertexArray(0)

    def resizeGL(self, w: int, h: int):
        gl.glViewport(0, 0, w, h)
        self._proj = QMatrix4x4()
        self._proj.perspective(45.0, w / max(h, 1), 0.05, 200.0)

    def paintGL(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        cam = self._camera_pos()
        view = QMatrix4x4()
        view.lookAt(
            QVector3D(*cam),
            QVector3D(*self._target),
            QVector3D(0, 1, 0),
        )
        model = QMatrix4x4()
        vp = self._proj * view

        # ── Grid ────────────────────────────────────────────────────────────
        if self.show_grid and self._grid_shader:
            gl.glUseProgram(self._grid_shader)
            gl.glUniformMatrix4fv(
                gl.glGetUniformLocation(self._grid_shader, "uVP"),
                1, gl.GL_FALSE, _mat4_data(vp),
            )
            gl.glBindVertexArray(self._grid_vao)
            gl.glDrawArrays(gl.GL_LINES, 0, self._grid_n)
            gl.glBindVertexArray(0)

        # ── Modelo ──────────────────────────────────────────────────────────
        if self._n_indices > 0 and self._shader:
            gl.glUseProgram(self._shader)

            # Matrices
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(self._shader,"uModel"),      1,gl.GL_FALSE,_mat4_data(model))
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(self._shader,"uView"),       1,gl.GL_FALSE,_mat4_data(view))
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(self._shader,"uProjection"), 1,gl.GL_FALSE,_mat4_data(self._proj))

            # Normal matrix = transpose(inverse(model)) — para model=identidad es identidad
            nm_data = np.eye(3, dtype=np.float32).flatten()
            gl.glUniformMatrix3fv(gl.glGetUniformLocation(self._shader,"uNormalMatrix"),1,gl.GL_FALSE,nm_data)

            gl.glUniform3f(gl.glGetUniformLocation(self._shader,"uCamPos"),   *cam)
            gl.glUniform1i(gl.glGetUniformLocation(self._shader,"uWireframe"), int(self.wireframe))
            gl.glUniform3f(gl.glGetUniformLocation(self._shader,"uBaseColor"),*self.base_color)

            if self.wireframe:
                gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
            else:
                gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

            gl.glBindVertexArray(self._vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self._n_indices, gl.GL_UNSIGNED_INT, None)
            gl.glBindVertexArray(0)
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

        gl.glUseProgram(0)

    # ── Cámara ────────────────────────────────────────────────────────────────

    def _camera_pos(self) -> np.ndarray:
        x = np.cos(self._pitch) * np.sin(self._yaw) * self._zoom
        y = np.sin(self._pitch) * self._zoom
        z = np.cos(self._pitch) * np.cos(self._yaw) * self._zoom
        return self._target + np.array([x, y, z], dtype=np.float32)

    def mousePressEvent(self, event):
        self._last_pos = event.position()

    def mouseMoveEvent(self, event):
        dx = event.position().x() - self._last_pos.x()
        dy = event.position().y() - self._last_pos.y()
        self._last_pos = event.position()
        if event.buttons() & Qt.LeftButton:
            self._yaw   -= dx * 0.012
            self._pitch  = float(np.clip(self._pitch + dy * 0.012, -1.45, 1.45))
        elif event.buttons() & Qt.MiddleButton:
            # Pan
            right = np.cross(self._camera_pos() - self._target, np.array([0,1,0],dtype=np.float32))
            right_n = right / (np.linalg.norm(right) + 1e-9)
            self._target += right_n * dx * 0.004 * self._zoom
            self._target[1] -= dy * 0.004 * self._zoom
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._zoom = float(np.clip(self._zoom * (0.9 if delta > 0 else 1.1), 0.2, 50.0))
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_W:
            self.set_wireframe(not self.wireframe)
        elif key == Qt.Key_R:
            self._yaw, self._pitch, self._zoom = 0.4, 0.25, 3.0
            self._target = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            self.update()


def _mat4_data(m: QMatrix4x4):
    return np.array(m.data(), dtype=np.float32)
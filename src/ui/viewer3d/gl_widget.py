# src/ui/viewer3d/gl_widget.py
"""
Visor OpenGL 3D para FLVER de Elden Ring.

Controles de navegación:
  ● Orbitar    : clic izquierdo + arrastrar
  ● Pan        : clic medio + arrastrar  |  Espacio + clic izquierdo
  ● Zoom       : rueda del ratón
  ● Reset      : doble clic  |  tecla [R]
  ● Wireframe  : tecla [W]
  ● Numpad 1   : vista frontal
  ● Numpad 3   : vista lateral
  ● Numpad 7   : vista superior
"""
import numpy as np
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMatrix4x4, QVector3D, QSurfaceFormat, QCursor
from PySide6.QtCore import Qt, QPoint, QTimer
import OpenGL.GL as gl
from OpenGL.GL import shaders
from loguru import logger


# ─────────────────────────────────────────────────────────────────────────────
# GLSL Shaders
# ─────────────────────────────────────────────────────────────────────────────

_VERT = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNorm;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProj;
uniform mat3 uNM;       // normal matrix

out vec3 vWorldPos;
out vec3 vNorm;
out vec3 vViewPos;

void main(){
    vec4 wp = uModel * vec4(aPos, 1.0);
    vWorldPos = wp.xyz;
    vNorm     = normalize(uNM * aNorm);
    gl_Position = uProj * uView * wp;
}
"""

_FRAG = """
#version 330 core
in vec3 vWorldPos;
in vec3 vNorm;

out vec4 FragColor;

uniform vec3 uCamPos;
uniform vec3 uBaseColor;
uniform bool uWireframe;
uniform bool uFlat;         // flat shading (normales por frag)

void main(){
    vec3 N = uFlat
        ? normalize(cross(dFdx(vWorldPos), dFdy(vWorldPos)))
        : normalize(vNorm);

    if(uWireframe){
        FragColor = vec4(0.15, 0.75, 1.0, 1.0);
        return;
    }

    // Tres luces: key, fill, rim
    vec3 L1 = normalize(vec3( 1.4,  2.0,  1.2));
    vec3 L2 = normalize(vec3(-0.8,  0.5, -0.6));
    vec3 L3 = normalize(vec3( 0.0, -1.0, -0.5));  // rim/bottom

    float d1 = max(dot(N, L1), 0.0);
    float d2 = max(dot(N, L2), 0.0) * 0.30;
    float d3 = max(dot(N, L3), 0.0) * 0.12;

    // Especular Blinn-Phong (key light)
    vec3 V  = normalize(uCamPos - vWorldPos);
    vec3 H  = normalize(L1 + V);
    float sp = pow(max(dot(N, H), 0.0), 48.0) * 0.45;

    vec3 ambient  = uBaseColor * 0.14;
    vec3 diffuse  = uBaseColor * (d1 + d2 + d3);
    vec3 specular = vec3(sp * 0.7);
    vec3 color    = ambient + diffuse + specular;

    // Tonemapping (Reinhard)
    color = color / (color + vec3(0.65));
    // Gamma
    color = pow(clamp(color, 0.0, 1.0), vec3(1.0/2.2));

    FragColor = vec4(color, 1.0);
}
"""

_GRID_VERT = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uVP;
void main(){ gl_Position = uVP * vec4(aPos, 1.0); }
"""

_GRID_FRAG = """
#version 330 core
out vec4 FragColor;
uniform vec4 uColor;
void main(){ FragColor = uColor; }
"""

_OVERLAY_VERT = """
#version 330 core
layout(location = 0) in vec2 aPos;
out vec2 vUV;
void main(){ vUV = aPos * 0.5 + 0.5; gl_Position = vec4(aPos, 0.0, 1.0); }
"""

_OVERLAY_FRAG = """
#version 330 core
in vec2 vUV;
out vec4 FragColor;
uniform sampler2D uTex;
void main(){ FragColor = texture(uTex, vUV); }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mat4(m: QMatrix4x4) -> np.ndarray:
    return np.array(m.data(), dtype=np.float32)


def _compute_normals(verts: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Per-vertex normals via face-normal accumulation."""
    n  = len(verts)
    nm = np.zeros((n, 3), dtype=np.float32)
    tri = indices.reshape(-1, 3).astype(np.int64)
    v0, v1, v2 = verts[tri[:,0]], verts[tri[:,1]], verts[tri[:,2]]
    fn = np.cross(v1 - v0, v2 - v0)
    np.add.at(nm, tri[:,0], fn)
    np.add.at(nm, tri[:,1], fn)
    np.add.at(nm, tri[:,2], fn)
    lens = np.linalg.norm(nm, axis=1, keepdims=True)
    lens = np.where(lens == 0, 1.0, lens)
    return (nm / lens).astype(np.float32)


def _make_grid(half=3.0, div=24) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (main_lines, axis_lines)."""
    main, axis = [], []
    step = half * 2 / div
    for i in range(div + 1):
        v = -half + i * step
        if abs(v) < 1e-4:
            continue
        main += [v,0,-half,  v,0,half]
        main += [-half,0,v,  half,0,v]
    # Ejes
    axis += [-half,0,0,  half,0,0]   # X rojo
    axis += [0,-half,0,  0,half,0]   # Y verde
    axis += [0,0,-half,  0,0,half]   # Z azul
    return np.array(main, np.float32), np.array(axis, np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Widget
# ─────────────────────────────────────────────────────────────────────────────

class GLViewerWidget(QOpenGLWidget):

    def __init__(self, parent=None):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setSamples(4)
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)
        super().__init__(parent)
        self.setMinimumSize(400, 380)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # ── Cámara ────────────────────────────────────────────────────────────
        self._yaw    = 0.5          # radianes
        self._pitch  = 0.22
        self._zoom   = 3.2
        self._target = np.array([0.0, 1.0, 0.0], np.float32)

        # ── Estado ratón ──────────────────────────────────────────────────────
        self._last_pos    = QPoint()
        self._space_held  = False   # Espacio = modo pan temporal

        # ── Mesh ──────────────────────────────────────────────────────────────
        self._verts:   np.ndarray | None = None
        self._indices: np.ndarray | None = None
        self._n_idx = 0

        # ── Opciones ──────────────────────────────────────────────────────────
        self.wireframe  = False
        self.flat_shade = True
        self.show_grid  = True
        self.base_color = np.array([0.60, 0.58, 0.56], np.float32)

        # ── GL handles (inicializados en initializeGL) ─────────────────────────
        self._sh = self._gsh = None
        self._vao = self._vbo = self._nbo = self._ebo = None
        self._grid_vao = self._grid_vbo = None
        self._axis_vao = self._axis_vbo = None
        self._proj = QMatrix4x4()

        # Tooltip de controles
        self.setToolTip(
            "🖱 Orbitar: clic izquierdo\n"
            "🖱 Pan: clic medio  /  Espacio+clic izq\n"
            "🖱 Zoom: rueda\n"
            "⌨ W: wireframe  R: reset  "
            "Num1: frontal  Num3: lateral  Num7: superior"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def load_mesh(self, verts_flat: np.ndarray, indices: np.ndarray):
        self._verts   = verts_flat.reshape(-1, 3).astype(np.float32)
        self._indices = indices.astype(np.uint32)
        self._n_idx   = len(self._indices)
        self.makeCurrent()
        self._upload_mesh()
        self.doneCurrent()
        self._reset_cam_to_model()
        self.update()

    def clear_mesh(self):
        self._verts = None
        self._indices = None
        self._n_idx = 0
        self.update()

    def set_wireframe(self, on: bool):
        self.wireframe = on
        self.update()

    def reset_camera(self):
        self._yaw    = 0.5
        self._pitch  = 0.22
        self._zoom   = 3.2
        self._target = np.array([0.0, 1.0, 0.0], np.float32)
        self.update()

    # ─────────────────────────────────────────────────────────────────────────
    # GL lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def initializeGL(self):
        gl.glClearColor(0.08, 0.08, 0.10, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(gl.GL_MULTISAMPLE)

        # Compilar shaders
        self._sh  = shaders.compileProgram(
            shaders.compileShader(_VERT, gl.GL_VERTEX_SHADER),
            shaders.compileShader(_FRAG, gl.GL_FRAGMENT_SHADER),
        )
        self._gsh = shaders.compileProgram(
            shaders.compileShader(_GRID_VERT, gl.GL_VERTEX_SHADER),
            shaders.compileShader(_GRID_FRAG, gl.GL_FRAGMENT_SHADER),
        )

        # VAOs para el modelo
        self._vao = gl.glGenVertexArrays(1)
        self._vbo = gl.glGenBuffers(1)
        self._nbo = gl.glGenBuffers(1)
        self._ebo = gl.glGenBuffers(1)

        # Grid
        self._grid_vao = gl.glGenVertexArrays(1)
        self._grid_vbo = gl.glGenBuffers(1)
        self._axis_vao = gl.glGenVertexArrays(1)
        self._axis_vbo = gl.glGenBuffers(1)

        main_g, axis_g = _make_grid()
        self._grid_n = len(main_g) // 3
        self._axis_n = len(axis_g) // 3

        for vao, vbo, gdata in [
            (self._grid_vao, self._grid_vbo, main_g),
            (self._axis_vao, self._axis_vbo, axis_g),
        ]:
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, gdata.nbytes, gdata, gl.GL_STATIC_DRAW)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
            gl.glEnableVertexAttribArray(0)
        gl.glBindVertexArray(0)

    def _upload_mesh(self):
        if self._verts is None or len(self._verts) < 3:
            return
        normals = _compute_normals(self._verts, self._indices)

        gl.glBindVertexArray(self._vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, self._verts.nbytes, self._verts, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
        gl.glEnableVertexAttribArray(0)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._nbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, normals.nbytes, normals, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
        gl.glEnableVertexAttribArray(1)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, gl.GL_STATIC_DRAW)

        gl.glBindVertexArray(0)

    def resizeGL(self, w, h):
        gl.glViewport(0, 0, w, h)
        self._proj = QMatrix4x4()
        self._proj.perspective(45.0, w / max(h, 1), 0.01, 500.0)

    def paintGL(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        cam = self._cam_pos()
        view = QMatrix4x4()
        view.lookAt(
            QVector3D(*cam.tolist()),
            QVector3D(*self._target.tolist()),
            QVector3D(0, 1, 0),
        )
        model = QMatrix4x4()
        vp = self._proj * view

        # ── Grid ──────────────────────────────────────────────────────────────
        if self.show_grid and self._gsh:
            gl.glUseProgram(self._gsh)
            loc_vp = gl.glGetUniformLocation(self._gsh, "uVP")
            loc_col= gl.glGetUniformLocation(self._gsh, "uColor")
            gl.glUniformMatrix4fv(loc_vp, 1, gl.GL_FALSE, _mat4(vp))

            # Líneas principales
            gl.glUniform4f(loc_col, 0.22, 0.22, 0.26, 0.7)
            gl.glBindVertexArray(self._grid_vao)
            gl.glDrawArrays(gl.GL_LINES, 0, self._grid_n)

            # Ejes (X=R, Y=G, Z=B) — dibujamos los 3 segmentos con colores distintos
            gl.glBindVertexArray(self._axis_vao)
            # X
            gl.glUniform4f(loc_col, 0.85, 0.25, 0.25, 0.9)
            gl.glDrawArrays(gl.GL_LINES, 0, 2)
            # Y
            gl.glUniform4f(loc_col, 0.25, 0.85, 0.25, 0.9)
            gl.glDrawArrays(gl.GL_LINES, 2, 2)
            # Z
            gl.glUniform4f(loc_col, 0.25, 0.45, 0.95, 0.9)
            gl.glDrawArrays(gl.GL_LINES, 4, 2)

            gl.glBindVertexArray(0)

        # ── Modelo ────────────────────────────────────────────────────────────
        if self._n_idx > 0 and self._sh:
            gl.glUseProgram(self._sh)

            def uloc(name): return gl.glGetUniformLocation(self._sh, name)

            gl.glUniformMatrix4fv(uloc("uModel"), 1, gl.GL_FALSE, _mat4(model))
            gl.glUniformMatrix4fv(uloc("uView"),  1, gl.GL_FALSE, _mat4(view))
            gl.glUniformMatrix4fv(uloc("uProj"),  1, gl.GL_FALSE, _mat4(self._proj))
            gl.glUniformMatrix3fv(uloc("uNM"),    1, gl.GL_FALSE, np.eye(3, dtype=np.float32))
            gl.glUniform3f(uloc("uCamPos"),  *cam.tolist())
            gl.glUniform3f(uloc("uBaseColor"), *self.base_color.tolist())
            gl.glUniform1i(uloc("uWireframe"), int(self.wireframe))
            gl.glUniform1i(uloc("uFlat"),      int(self.flat_shade))

            if self.wireframe:
                gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
                gl.glLineWidth(1.0)
            else:
                gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
                gl.glEnable(gl.GL_CULL_FACE)
                gl.glCullFace(gl.GL_BACK)

            gl.glBindVertexArray(self._vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self._n_idx, gl.GL_UNSIGNED_INT, None)
            gl.glBindVertexArray(0)

            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
            gl.glDisable(gl.GL_CULL_FACE)

        gl.glUseProgram(0)

        # ── HUD de controles (texto Qt pintado sobre GL) ──────────────────────
        self._draw_hud()

    def _draw_hud(self):
        """Dibuja el HUD de controles en la esquina inferior izquierda."""
        from PySide6.QtGui import QPainter, QColor, QFont
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing)

        font = QFont("Consolas", 9)
        painter.setFont(font)

        lines = [
            "LMB Arrastrar : Orbitar",
            "MMB / Spc+LMB : Pan",
            "Rueda          : Zoom",
            "W : Wireframe   R : Reset",
            "Doble clic     : Reset",
        ]
        x, y = 8, self.height() - len(lines) * 16 - 6
        for line in lines:
            painter.setPen(QColor(0, 0, 0, 120))
            painter.drawText(x+1, y+1, line)
            painter.setPen(QColor(180, 180, 180, 200))
            painter.drawText(x, y, line)
            y += 16
        painter.end()

    # ─────────────────────────────────────────────────────────────────────────
    # Cámara
    # ─────────────────────────────────────────────────────────────────────────

    def _cam_pos(self) -> np.ndarray:
        cp = np.cos(self._pitch)
        return self._target + self._zoom * np.array([
            cp * np.sin(self._yaw),
            np.sin(self._pitch),
            cp * np.cos(self._yaw),
        ], np.float32)

    def _reset_cam_to_model(self):
        """Ajusta cámara al bounding box del modelo cargado."""
        if self._verts is None:
            return
        mn = self._verts.min(axis=0)
        mx = self._verts.max(axis=0)
        self._target = ((mn + mx) * 0.5).astype(np.float32)
        ext = float((mx - mn).max())
        self._zoom  = max(ext * 1.6, 0.5)
        self._yaw   = 0.5
        self._pitch = 0.22

    def _pan(self, dx: float, dy: float):
        """Mueve el target en el plano de la cámara."""
        cam = self._cam_pos()
        fwd = self._target - cam
        fwd /= np.linalg.norm(fwd) + 1e-9
        up  = np.array([0.0, 1.0, 0.0], np.float32)
        right = np.cross(fwd, up)
        right /= np.linalg.norm(right) + 1e-9
        real_up = np.cross(right, fwd)
        spd = self._zoom * 0.0012
        self._target -= right * dx * spd
        self._target += real_up * dy * spd

    # ─────────────────────────────────────────────────────────────────────────
    # Eventos de ratón / teclado
    # ─────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        self._last_pos = ev.position()
        self.setFocus()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.reset_camera()

    def mouseMoveEvent(self, ev):
        dx = ev.position().x() - self._last_pos.x()
        dy = ev.position().y() - self._last_pos.y()
        self._last_pos = ev.position()

        lb = ev.buttons() & Qt.LeftButton
        mb = ev.buttons() & Qt.MiddleButton

        if mb or (lb and self._space_held):
            self._pan(dx, dy)
        elif lb:
            self._yaw   -= dx * 0.010
            self._pitch  = float(np.clip(self._pitch + dy * 0.010, -1.48, 1.48))

        self.update()

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        factor = 0.88 if delta > 0 else 1.13
        self._zoom = float(np.clip(self._zoom * factor, 0.05, 200.0))
        self.update()

    def keyPressEvent(self, ev):
        k = ev.key()
        if k == Qt.Key_Space:
            self._space_held = True
            self.setCursor(Qt.SizeAllCursor)
        elif k == Qt.Key_W:
            self.wireframe = not self.wireframe
            self.update()
        elif k == Qt.Key_R:
            self.reset_camera()
        elif k == Qt.Key_F:
            self.flat_shade = not self.flat_shade
            self.update()
        # Vistas numpad
        elif k == Qt.Key_1:    # frontal (Z-)
            self._yaw, self._pitch = 0.0, 0.0
            self.update()
        elif k == Qt.Key_3:    # lateral (X-)
            self._yaw, self._pitch = -np.pi/2, 0.0
            self.update()
        elif k == Qt.Key_7:    # superior
            self._yaw, self._pitch = 0.0, np.pi/2 - 0.01
            self.update()
        elif k == Qt.Key_5:    # trasero
            self._yaw, self._pitch = np.pi, 0.0
            self.update()
        else:
            super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self._space_held = False
            self.setCursor(Qt.ArrowCursor)
        else:
            super().keyReleaseEvent(ev)
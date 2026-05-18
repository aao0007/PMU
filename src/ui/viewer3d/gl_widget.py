# src/ui/viewer3d/gl_widget.py
"""
Visor OpenGL 3.3 Core Profile para modelos FLVER de Elden Ring.

Modos de visualización:
  SOLID     → gris metálico, normales suaves calculadas, lighting Phong
  WIREFRAME → malla de aristas sobre fondo oscuro  
  TEXTURED  → colores derivados de normales (simula el look del FLVER Editor
               que usa gradientes de normal-color como proxy visual)

Controles:
  LMB drag       → Orbitar
  MMB drag       → Pan
  Espacio+LMB    → Pan alternativo (estilo Maya)
  Rueda          → Zoom
  Doble clic LMB → Reset cámara
  R              → Reset cámara
  W              → Ciclar modo render (Solid → Wire → Textured)
  1/3/7/5        → Vistas preset
"""

import math
import numpy as np
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import (
    QMatrix4x4, QVector3D, QSurfaceFormat,
    QPainter, QColor, QFont, QFontMetrics,
)
from PySide6.QtCore import Qt, QPoint, Signal
import OpenGL.GL as gl
from OpenGL.GL import shaders
from loguru import logger


# ─────────────────────────────────────────────────────────────────────────────
# Modos
# ─────────────────────────────────────────────────────────────────────────────
class RenderMode:
    SOLID    = 0
    WIRE     = 1
    TEXTURED = 2
    _NAMES   = ["Solid", "Wireframe", "Textured"]
    _ICONS   = ["⬛", "⬜", "🎨"]

    @staticmethod
    def label(m): return f"{RenderMode._ICONS[m]} {RenderMode._NAMES[m]}"


# ─────────────────────────────────────────────────────────────────────────────
# GLSL — Solid + Textured compartidos, Wireframe separado
# ─────────────────────────────────────────────────────────────────────────────

# Shader principal: Solid y Textured
_MAIN_VERT = """
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;

uniform mat4 uMVP;
uniform mat4 uModel;
uniform mat3 uNM;

out vec3 vNorm;
out vec3 vWorld;
out vec3 vLocalPos;

void main(){
    vec4 world  = uModel * vec4(aPos, 1.0);
    vWorld      = world.xyz;
    vLocalPos   = aPos;
    vNorm       = normalize(uNM * aNorm);
    gl_Position = uMVP * vec4(aPos, 1.0);
}
"""

_MAIN_FRAG = """
#version 330 core
in vec3 vNorm;
in vec3 vWorld;
in vec3 vLocalPos;

out vec4 FragColor;

uniform vec3 uCamPos;
uniform int  uMode;      // 0=solid 2=textured
uniform vec3 uBaseColor;

// Calcula color FLVER-style: usa normales como color proxy
vec3 flver_color(vec3 N){
    // Igual que FLVER Editor: mapea normales a espacio de color
    vec3 c = abs(N);
    // Mezcla componentes para dar variedad
    vec3 rgb = vec3(
        c.x * 0.6 + c.z * 0.4,
        c.y * 0.5 + c.x * 0.3,
        c.z * 0.5 + c.y * 0.3
    );
    return clamp(rgb, 0.1, 1.0);
}

void main(){
    // Normal smooth (calculada en vertex shader)
    vec3 N = normalize(vNorm);
    
    if(uMode == 2){
        // Textured/FLVER mode
        vec3 baseCol = flver_color(N);
        // Iluminación suave para dar volumen
        vec3 L1 = normalize(vec3(0.8, 1.5, 1.0));
        vec3 L2 = normalize(vec3(-0.5, 0.3, -0.8));
        float d1 = max(dot(N, L1), 0.0);
        float d2 = max(dot(N, L2), 0.0) * 0.25;
        vec3 V  = normalize(uCamPos - vWorld);
        vec3 H  = normalize(L1 + V);
        float sp = pow(max(dot(N, H), 0.0), 80.0) * 0.3;
        vec3 col = baseCol * (0.25 + d1 + d2) + vec3(sp);
        col = col / (col + vec3(0.6));
        col = pow(clamp(col, 0.0, 1.0), vec3(1.0/2.2));
        FragColor = vec4(col, 1.0);
        return;
    }

    // Solid mode — Phong 3 luces
    vec3 L1 = normalize(vec3( 1.2,  2.0,  1.0));
    vec3 L2 = normalize(vec3(-0.7,  0.4, -0.5));
    vec3 L3 = normalize(vec3( 0.0, -0.8, -0.3));

    float d1 = max(dot(N, L1), 0.0);
    float d2 = max(dot(N, L2), 0.0) * 0.25;
    float d3 = max(dot(N, L3), 0.0) * 0.08;

    vec3 V   = normalize(uCamPos - vWorld);
    vec3 H   = normalize(L1 + V);
    float sp = pow(max(dot(N, H), 0.0), 60.0) * 0.35;

    vec3 amb = uBaseColor * 0.14;
    vec3 dif = uBaseColor * (d1 + d2 + d3);
    vec3 spe = vec3(sp * 0.6);
    vec3 col = amb + dif + spe;

    col = col / (col + vec3(0.65));
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0/2.2));
    FragColor = vec4(col, 1.0);
}
"""

# Shader wireframe — usa geometry shader para calcular aristas
_WIRE_VERT = """
#version 330 core
layout(location=0) in vec3 aPos;
uniform mat4 uMVP;
void main(){ gl_Position = uMVP * vec4(aPos, 1.0); }
"""

_WIRE_FRAG = """
#version 330 core
out vec4 FragColor;
void main(){ FragColor = vec4(0.10, 0.72, 1.0, 1.0); }
"""

# Grid
_GRID_VERT = """
#version 330 core
layout(location=0) in vec3 aPos;
uniform mat4 uVP;
void main(){ gl_Position = uVP * vec4(aPos, 1.0); }
"""
_GRID_FRAG = """
#version 330 core
out vec4 FragColor;
uniform vec4 uColor;
void main(){ FragColor = uColor; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _m4(m: QMatrix4x4) -> np.ndarray:
    return np.array(m.data(), dtype=np.float32)


def _compute_normals(verts: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Per-vertex normals suavizados por face-normal accumulation."""
    n  = len(verts)
    nm = np.zeros((n, 3), np.float32)
    tri = idx.reshape(-1, 3).astype(np.int64)
    # Clip indices to valid range
    tri = np.clip(tri, 0, n - 1)
    v0, v1, v2 = verts[tri[:,0]], verts[tri[:,1]], verts[tri[:,2]]
    fn = np.cross(v1 - v0, v2 - v0)
    np.add.at(nm, tri[:,0], fn)
    np.add.at(nm, tri[:,1], fn)
    np.add.at(nm, tri[:,2], fn)
    lens = np.linalg.norm(nm, axis=1, keepdims=True)
    lens = np.where(lens == 0, 1.0, lens)
    return (nm / lens).astype(np.float32)


def _make_grid(half=3.0, div=24):
    main, axis = [], []
    step = half * 2 / div
    for i in range(div + 1):
        v = -half + i * step
        if abs(v) < 1e-5: continue
        main += [v,0,-half, v,0,half, -half,0,v, half,0,v]
    axis += [-half,0,0, half,0,0, 0,-half,0, 0,half,0, 0,0,-half, 0,0,half]
    return np.array(main, np.float32), np.array(axis, np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Widget
# ─────────────────────────────────────────────────────────────────────────────

class GLViewerWidget(QOpenGLWidget):

    render_mode_changed = Signal(int)

    _BG = {
        RenderMode.SOLID:    (0.08, 0.08, 0.10),
        RenderMode.WIRE:     (0.04, 0.04, 0.06),
        RenderMode.TEXTURED: (0.06, 0.06, 0.08),
    }

    def __init__(self, parent=None):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setSamples(4)
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)
        super().__init__(parent)

        self.setMinimumSize(300, 280)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # Cámara
        self._yaw    =  0.50
        self._pitch  =  0.22
        self._zoom   =  3.20
        self._target = np.array([0.0, 1.0, 0.0], np.float32)

        # Ratón
        self._last_pos   = QPoint()
        self._space_held = False

        # Malla
        self._verts:   np.ndarray | None = None
        self._indices: np.ndarray | None = None
        self._n_idx = 0

        # Opciones
        self.render_mode = RenderMode.SOLID
        self.show_grid   = True
        self.base_color  = np.array([0.60, 0.58, 0.56], np.float32)

        # GL handles
        self._sh_main  = None
        self._sh_wire  = None
        self._sh_grid  = None

        self._vao = self._vbo = self._nbo = self._ebo = None
        self._grid_vao = self._grid_vbo = None
        self._axis_vao = self._axis_vbo = None
        self._grid_n = self._axis_n = 0

        self._proj = QMatrix4x4()

    # ── Public API ────────────────────────────────────────────────────────────

    def load_mesh(self, verts_flat: np.ndarray, indices: np.ndarray):
        self._verts   = verts_flat.reshape(-1, 3).astype(np.float32)
        self._indices = indices.astype(np.uint32)
        self._n_idx   = len(self._indices)
        self.makeCurrent()
        self._upload_mesh()
        self.doneCurrent()
        self._fit_camera()
        self.update()

    def clear_mesh(self):
        self._verts = self._indices = None
        self._n_idx = 0
        self.update()

    def set_render_mode(self, mode: int):
        self.render_mode = mode
        bg = self._BG.get(mode, (0.08, 0.08, 0.10))
        self.makeCurrent()
        gl.glClearColor(*bg, 1.0)
        self.doneCurrent()
        self.render_mode_changed.emit(mode)
        self.update()

    def cycle_render_mode(self):
        self.set_render_mode((self.render_mode + 1) % 3)

    def reset_camera(self):
        self._yaw   = 0.50
        self._pitch = 0.22
        self._zoom  = 3.20
        self._target = np.array([0.0, 1.0, 0.0], np.float32)
        self.update()

    # ── GL lifecycle ──────────────────────────────────────────────────────────

    def initializeGL(self):
        bg = self._BG[RenderMode.SOLID]
        gl.glClearColor(*bg, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(gl.GL_MULTISAMPLE)

        try:
            self._sh_main = shaders.compileProgram(
                shaders.compileShader(_MAIN_VERT, gl.GL_VERTEX_SHADER),
                shaders.compileShader(_MAIN_FRAG, gl.GL_FRAGMENT_SHADER),
            )
            self._sh_wire = shaders.compileProgram(
                shaders.compileShader(_WIRE_VERT, gl.GL_VERTEX_SHADER),
                shaders.compileShader(_WIRE_FRAG, gl.GL_FRAGMENT_SHADER),
            )
            self._sh_grid = shaders.compileProgram(
                shaders.compileShader(_GRID_VERT, gl.GL_VERTEX_SHADER),
                shaders.compileShader(_GRID_FRAG, gl.GL_FRAGMENT_SHADER),
            )
        except Exception as e:
            logger.error(f"Shader compile error: {e}")
            raise

        # VAOs malla
        self._vao = gl.glGenVertexArrays(1)
        self._vbo = gl.glGenBuffers(1)
        self._nbo = gl.glGenBuffers(1)
        self._ebo = gl.glGenBuffers(1)

        # VAOs grid / ejes
        self._grid_vao = gl.glGenVertexArrays(1)
        self._grid_vbo = gl.glGenBuffers(1)
        self._axis_vao = gl.glGenVertexArrays(1)
        self._axis_vbo = gl.glGenBuffers(1)

        mg, ag = _make_grid()
        self._grid_n = len(mg) // 3
        self._axis_n = len(ag) // 3

        for vao, vbo, data in [
            (self._grid_vao, self._grid_vbo, mg),
            (self._axis_vao, self._axis_vbo, ag),
        ]:
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_STATIC_DRAW)
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
            QVector3D(float(cam[0]), float(cam[1]), float(cam[2])),
            QVector3D(float(self._target[0]), float(self._target[1]), float(self._target[2])),
            QVector3D(0, 1, 0),
        )
        model = QMatrix4x4()
        vp    = self._proj * view
        mvp   = self._proj * view * model

        # ── Grid ──────────────────────────────────────────────────────────────
        if self.show_grid and self._sh_grid:
            gl.glUseProgram(self._sh_grid)
            lVP  = gl.glGetUniformLocation(self._sh_grid, "uVP")
            lCol = gl.glGetUniformLocation(self._sh_grid, "uColor")
            gl.glUniformMatrix4fv(lVP, 1, gl.GL_FALSE, _m4(vp))

            # Líneas grid
            gl.glUniform4f(lCol, 0.18, 0.18, 0.22, 0.6)
            gl.glBindVertexArray(self._grid_vao)
            gl.glDrawArrays(gl.GL_LINES, 0, self._grid_n)

            # Ejes
            gl.glBindVertexArray(self._axis_vao)
            for start, col in [(0,(0.85,0.22,0.22,0.9)), (2,(0.22,0.82,0.22,0.9)), (4,(0.22,0.42,0.92,0.9))]:
                gl.glUniform4f(lCol, *col)
                gl.glDrawArrays(gl.GL_LINES, start, 2)

            gl.glBindVertexArray(0)

        # ── Modelo ────────────────────────────────────────────────────────────
        if self._n_idx <= 0:
            gl.glUseProgram(0)
            self._paint_hud()
            return

        if self.render_mode == RenderMode.WIRE:
            # Wireframe puro: líneas sobre el VAO principal
            gl.glUseProgram(self._sh_wire)
            lMVP = gl.glGetUniformLocation(self._sh_wire, "uMVP")
            gl.glUniformMatrix4fv(lMVP, 1, gl.GL_FALSE, _m4(mvp))
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
            gl.glLineWidth(1.0)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glBindVertexArray(self._vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self._n_idx, gl.GL_UNSIGNED_INT, None)
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

        else:
            # Solid o Textured
            gl.glUseProgram(self._sh_main)

            def u(n): return gl.glGetUniformLocation(self._sh_main, n)

            gl.glUniformMatrix4fv(u("uMVP"),    1, gl.GL_FALSE, _m4(mvp))
            gl.glUniformMatrix4fv(u("uModel"),  1, gl.GL_FALSE, _m4(model))
            # Normal matrix = identity para model=identity
            gl.glUniformMatrix3fv(u("uNM"),     1, gl.GL_FALSE, np.eye(3, dtype=np.float32))
            gl.glUniform3f(u("uCamPos"),   float(cam[0]), float(cam[1]), float(cam[2]))
            gl.glUniform3f(u("uBaseColor"),*self.base_color.tolist())
            gl.glUniform1i(u("uMode"),     self.render_mode)

            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
            # Doble cara para ver interior también (como FLVER Editor)
            gl.glDisable(gl.GL_CULL_FACE)

            gl.glBindVertexArray(self._vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self._n_idx, gl.GL_UNSIGNED_INT, None)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
        gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
        gl.glDisable(gl.GL_CULL_FACE)

        self._paint_hud()

    def _paint_hud(self):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing)

        # Modo actual (esquina superior izquierda)
        label = RenderMode.label(self.render_mode)
        cols  = {RenderMode.SOLID: QColor(160,200,255), RenderMode.WIRE: QColor(30,190,255), RenderMode.TEXTURED: QColor(140,255,180)}
        c = cols.get(self.render_mode, QColor(200,200,200))
        font = QFont("Consolas", 10, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(0,0,0,140))
        painter.drawText(11, 23, label)
        painter.setPen(c)
        painter.drawText(10, 22, label)

        # Stats (esquina superior derecha)
        if self._n_idx > 0 and self._verts is not None:
            stats = f"{len(self._verts):,}v · {self._n_idx//3:,}t"
            fm = QFontMetrics(font)
            tw = fm.horizontalAdvance(stats)
            painter.setPen(QColor(0,0,0,130))
            painter.drawText(self.width() - tw - 9, 23, stats)
            painter.setPen(QColor(140,210,140,220))
            painter.drawText(self.width() - tw - 10, 22, stats)

        # Controles (esquina inferior izquierda)
        ctrl_font = QFont("Consolas", 8)
        painter.setFont(ctrl_font)
        lines = ["LMB:Orbitar  MMB/Spc:Pan  Rueda:Zoom", "W:Modo  R:Reset  1/3/7:Vista"]
        y = self.height() - len(lines)*14 - 5
        for line in lines:
            painter.setPen(QColor(0,0,0,110))
            painter.drawText(10, y+1, line)
            painter.setPen(QColor(155,155,155,170))
            painter.drawText(9, y, line)
            y += 14

        painter.end()

    # ── Cámara ────────────────────────────────────────────────────────────────

    def _cam_pos(self) -> np.ndarray:
        cp = math.cos(self._pitch)
        return self._target + self._zoom * np.array([
            cp * math.sin(self._yaw),
            math.sin(self._pitch),
            cp * math.cos(self._yaw),
        ], np.float32)

    def _fit_camera(self):
        if self._verts is None: return
        mn = self._verts.min(axis=0)
        mx = self._verts.max(axis=0)
        self._target = ((mn + mx) * 0.5).astype(np.float32)
        self._zoom   = max(float((mx - mn).max()) * 1.8, 0.3)
        self._yaw    = 0.50
        self._pitch  = 0.22

    def _pan(self, dx, dy):
        cam  = self._cam_pos()
        fwd  = self._target - cam;  fwd  /= np.linalg.norm(fwd)  + 1e-9
        right = np.cross(fwd, [0,1,0]); right /= np.linalg.norm(right) + 1e-9
        up   = np.cross(right, fwd)
        spd  = self._zoom * 0.0012
        self._target -= right * dx * spd
        self._target += up    * dy * spd

    # ── Eventos ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        self._last_pos = ev.position(); self.setFocus()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton: self.reset_camera()

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
        f = 0.87 if ev.angleDelta().y() > 0 else 1.15
        self._zoom = float(np.clip(self._zoom * f, 0.04, 300.0))
        self.update()

    def keyPressEvent(self, ev):
        k = ev.key()
        if   k == Qt.Key_Space: self._space_held = True;  self.setCursor(Qt.SizeAllCursor)
        elif k == Qt.Key_W:     self.cycle_render_mode()
        elif k == Qt.Key_R:     self.reset_camera()
        elif k == Qt.Key_1:     self._yaw, self._pitch = 0.0, 0.0;            self.update()
        elif k == Qt.Key_3:     self._yaw, self._pitch = -math.pi/2, 0.0;     self.update()
        elif k == Qt.Key_7:     self._yaw, self._pitch = 0.0, 1.47;           self.update()
        elif k == Qt.Key_5:     self._yaw, self._pitch = math.pi, 0.0;        self.update()
        else: super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self._space_held = False; self.setCursor(Qt.ArrowCursor)
        else: super().keyReleaseEvent(ev)
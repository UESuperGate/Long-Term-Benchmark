package org.signal.mediasend.screens.edit.image

enum class BrushTool { DRAW, HIGHLIGHT }
data class BrushWidths(val draw: Float = 0.5f) { fun with(tool: BrushTool, fraction: Float) = copy(draw = fraction) }
class BrushWidthsState(value: BrushWidths)

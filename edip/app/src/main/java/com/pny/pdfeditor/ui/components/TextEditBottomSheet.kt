package com.pny.pdfeditor.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pny.pdfeditor.data.model.SpanDetail
import com.pny.pdfeditor.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TextEditBottomSheet(
    span: SpanDetail,
    isDragMode: Boolean,
    onDragModeChange: (Boolean) -> Unit,
    onApplyEdit: (newText: String, fontName: String, fontSize: Float, colorRgb: List<Float>) -> Unit,
    onDeleteText: () -> Unit,
    onDismiss: () -> Unit
) {
    val isFontBold = remember(span) {
        val f = span.font.lowercase()
        f.contains("bold") || f.contains("hebo") || f.contains("tibo") || f.contains("cobo") || ((span.flags and 16) != 0)
    }
    val isFontItalic = remember(span) {
        val f = span.font.lowercase()
        f.contains("italic") || f.contains("oblique") || ((span.flags and 2) != 0)
    }

    var isBold by remember(span) { mutableStateOf(isFontBold) }
    var isItalic by remember(span) { mutableStateOf(isFontItalic) }

    var textValue by remember(span) { mutableStateOf(span.text) }
    var fontSize by remember(span) { mutableFloatStateOf(span.size) }
    var fontName by remember(span) {
        val f = span.font.lowercase()
        mutableStateOf(
            when {
                f.contains("time") || f.contains("serif") -> "tiro"
                f.contains("couri") || f.contains("mono") -> "cour"
                else -> "helv"
            }
        )
    }

    // Default colors: Black, Dark Gray, Blue, Red, Green
    val colorOptions = listOf(
        Pair(Color(0xFF000000), listOf(0f, 0f, 0f)),
        Pair(Color(0xFF2563EB), listOf(0.145f, 0.388f, 0.921f)),
        Pair(Color(0xFFDC2626), listOf(0.862f, 0.149f, 0.149f)),
        Pair(Color(0xFF16A34A), listOf(0.086f, 0.639f, 0.290f)),
        Pair(Color(0xFF4B5563), listOf(0.294f, 0.333f, 0.388f))
    )
    var selectedColorRgb by remember(span) {
        mutableStateOf(
            if (span.color_rgb.size == 3) span.color_rgb else listOf(0f, 0f, 0f)
        )
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = DarkSurface,
        dragHandle = { BottomSheetDefaults.DragHandle(color = TextSecondary) },
        shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 10.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "EDIT PDF TEXT OBJECT",
                    color = AccentBlue,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold
                )
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Multiline text input with live bold & italic reflection
            OutlinedTextField(
                value = textValue,
                onValueChange = { textValue = it },
                label = { Text("Text content (Press Enter for new line)") },
                modifier = Modifier.fillMaxWidth(),
                maxLines = 4,
                textStyle = androidx.compose.ui.text.TextStyle(
                    fontWeight = if (isBold) FontWeight.Bold else FontWeight.Normal,
                    fontStyle = if (isItalic) androidx.compose.ui.text.font.FontStyle.Italic else androidx.compose.ui.text.font.FontStyle.Normal,
                    fontSize = 15.sp,
                    color = TextPrimary
                ),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = AccentBlue,
                    unfocusedBorderColor = DarkSurfaceVariant,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary
                )
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Font, Bold, Italic & Size Controls
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Font Family & Weight Chips
                Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    listOf("helv" to "Sans", "tiro" to "Serif", "cour" to "Mono").forEach { (code, label) ->
                        val isSelected = fontName == code
                        FilterChip(
                            selected = isSelected,
                            onClick = { fontName = code },
                            label = { Text(label, fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = AccentBlue,
                                selectedLabelColor = Color.White
                            )
                        )
                    }

                    // Bold Toggle Button
                    FilterChip(
                        selected = isBold,
                        onClick = { isBold = !isBold },
                        label = { Text("B", fontSize = 12.sp, fontWeight = FontWeight.ExtraBold) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = AccentBlue,
                            selectedLabelColor = Color.White
                        )
                    )

                    // Italic Toggle Button
                    FilterChip(
                        selected = isItalic,
                        onClick = { isItalic = !isItalic },
                        label = { Text("I", fontSize = 12.sp, fontStyle = androidx.compose.ui.text.font.FontStyle.Italic, fontWeight = FontWeight.Bold) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = AccentBlue,
                            selectedLabelColor = Color.White
                        )
                    )
                }

                // Font Size Stepper
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    IconButton(
                        onClick = { if (fontSize > 4f) fontSize -= 1f },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.Remove, contentDescription = "Decrease", tint = TextPrimary)
                    }
                    Text(
                        text = "${fontSize.toInt()}pt",
                        color = TextPrimary,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    IconButton(
                        onClick = { fontSize += 1f },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.Add, contentDescription = "Increase", tint = TextPrimary)
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Color Palette & Drag Mode Toggle
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Color circles
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    colorOptions.forEach { (c, rgb) ->
                        val isSelected = selectedColorRgb == rgb
                        Box(
                            modifier = Modifier
                                .size(28.dp)
                                .clip(CircleShape)
                                .background(c)
                                .border(
                                    width = if (isSelected) 2.dp else 0.dp,
                                    color = if (isSelected) AccentBlueLight else Color.Transparent,
                                    shape = CircleShape
                                )
                                .clickable { selectedColorRgb = rgb }
                        )
                    }
                }

                // Drag Mode Toggle Switch
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Drag text", fontSize = 12.sp, color = TextSecondary)
                    Spacer(modifier = Modifier.width(6.dp))
                    Switch(
                        checked = isDragMode,
                        onCheckedChange = onDragModeChange,
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = AccentBlue,
                            checkedTrackColor = DarkSurfaceVariant
                        )
                    )
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Button(
                    onClick = {
                        val resolvedFont = when (fontName) {
                            "tiro" -> if (isBold && isItalic) "tibi" else if (isBold) "tibo" else if (isItalic) "tiit" else "tiro"
                            "cour" -> if (isBold && isItalic) "cobi" else if (isBold) "cobo" else if (isItalic) "coit" else "cour"
                            else -> if (isBold && isItalic) "hebi" else if (isBold) "hebo" else if (isItalic) "heit" else "helv"
                        }
                        onApplyEdit(textValue, resolvedFont, fontSize, selectedColorRgb)
                    },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = AccentBlue)
                ) {
                    Text("Apply Edit", fontWeight = FontWeight.Bold)
                }

                OutlinedButton(
                    onClick = onDeleteText,
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = DangerRed)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = "Delete")
                }
            }

            Spacer(modifier = Modifier.height(20.dp))
        }
    }
}

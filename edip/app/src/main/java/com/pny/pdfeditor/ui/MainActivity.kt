package com.pny.pdfeditor.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import com.pny.pdfeditor.ui.components.PdfCanvasView
import com.pny.pdfeditor.ui.components.TextEditBottomSheet
import com.pny.pdfeditor.ui.components.TextListBottomSheet
import com.pny.pdfeditor.ui.theme.*

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            EdipTheme {
                val context = LocalContext.current
                val docId by viewModel.currentDocId.collectAsState()
                val docName by viewModel.docName.collectAsState()
                val pageCount by viewModel.pageCount.collectAsState()
                val currentPageIndex by viewModel.currentPageIndex.collectAsState()
                val pageInfo by viewModel.currentPageInfo.collectAsState()
                val pageBitmap by viewModel.pageBitmap.collectAsState()
                val selectedSpan by viewModel.selectedSpan.collectAsState()
                val dragOffset by viewModel.dragOffset.collectAsState()
                val isDragMode by viewModel.isDragMode.collectAsState()
                val isLineMode by viewModel.isLineMode.collectAsState()
                val isLoading by viewModel.isLoading.collectAsState()
                val statusMessage by viewModel.statusMessage.collectAsState()

                var showTextListSheet by remember { mutableStateOf(false) }
                var showPageJumpDialog by remember { mutableStateOf(false) }
                var showAddTextDialog by remember { mutableStateOf(false) }

                val snackbarHostState = remember { SnackbarHostState() }

                // System file picker launcher
                val pdfPickerLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.GetContent()
                ) { uri: Uri? ->
                    uri?.let { viewModel.uploadPdf(context, it) }
                }

                // Show status notifications
                LaunchedEffect(statusMessage) {
                    statusMessage?.let {
                        snackbarHostState.showSnackbar(it)
                        viewModel.clearStatusMessage()
                    }
                }

                Scaffold(
                    snackbarHost = { SnackbarHost(snackbarHostState) },
                    topBar = {
                        TopAppBar(
                            title = {
                                Column {
                                    Text(
                                        text = docName,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Bold,
                                        maxLines = 1,
                                        color = TextPrimary
                                    )
                                    if (pageCount > 0) {
                                        Text(
                                            text = if (pageInfo?.text_blocks?.isEmpty() == true) "📸 Scanned Image (Tap OCR)" else if (isLineMode) "Line Mode (Tap line to edit)" else "Word Mode (Tap word to edit)",
                                            fontSize = 11.sp,
                                            color = if (pageInfo?.text_blocks?.isEmpty() == true) WarningColor else AccentBlueLight
                                        )
                                    }
                                }
                            },
                            actions = {
                                if (pageCount > 0) {
                                    // Line Mode vs Word Mode Toggle
                                    IconButton(onClick = { viewModel.setLineMode(!isLineMode) }) {
                                        Icon(
                                            if (isLineMode) Icons.Default.ViewStream else Icons.Default.Subtitles,
                                            contentDescription = if (isLineMode) "Line Mode" else "Word Mode",
                                            tint = if (isLineMode) AccentBlue else TextSecondary
                                        )
                                    }

                                    // Add Text Button
                                    IconButton(onClick = { showAddTextDialog = true }) {
                                        Icon(
                                            Icons.Default.Add,
                                            contentDescription = "Add Text",
                                            tint = AccentBlue
                                        )
                                    }

                                    // Edit All Text Sheet Button
                                    IconButton(onClick = { showTextListSheet = true }) {
                                        Icon(
                                            Icons.Default.Edit,
                                            contentDescription = "Edit Text List",
                                            tint = TextPrimary
                                        )
                                    }

                                    // Run OCR Button (for scanned documents)
                                    IconButton(onClick = { viewModel.runOcr() }) {
                                        Icon(
                                            Icons.Default.DocumentScanner,
                                            contentDescription = "Run OCR on Page",
                                            tint = if (pageInfo?.text_blocks?.isEmpty() == true) WarningColor else TextPrimary
                                        )
                                    }

                                    // Page Navigation Back
                                    IconButton(
                                        onClick = { viewModel.changePage(currentPageIndex - 1) },
                                        enabled = currentPageIndex > 0
                                    ) {
                                        Icon(
                                            Icons.AutoMirrored.Filled.ArrowBack,
                                            contentDescription = "Prev Page",
                                            tint = if (currentPageIndex > 0) TextPrimary else TextSecondary.copy(alpha = 0.4f)
                                        )
                                    }

                                    // Clickable Page Jumper Badge
                                    Surface(
                                        shape = RoundedCornerShape(8.dp),
                                        color = DarkSurfaceVariant,
                                        modifier = Modifier.clickable { showPageJumpDialog = true }
                                    ) {
                                        Text(
                                            text = "${currentPageIndex + 1}/$pageCount",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = AccentBlue,
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                        )
                                    }

                                    // Page Navigation Forward
                                    IconButton(
                                        onClick = { viewModel.changePage(currentPageIndex + 1) },
                                        enabled = currentPageIndex < pageCount - 1
                                    ) {
                                        Icon(
                                            Icons.AutoMirrored.Filled.ArrowForward,
                                            contentDescription = "Next Page",
                                            tint = if (currentPageIndex < pageCount - 1) TextPrimary else TextSecondary.copy(alpha = 0.4f)
                                        )
                                    }

                                    // Rotate Page
                                    IconButton(onClick = { viewModel.rotateCurrentPage() }) {
                                        Icon(Icons.Default.Refresh, contentDescription = "Rotate", tint = TextPrimary)
                                    }

                                    // Export / Share PDF
                                    IconButton(onClick = {
                                        viewModel.exportPdf(context) { exportedFile ->
                                            val shareUri = FileProvider.getUriForFile(
                                                context,
                                                "${context.packageName}.fileprovider",
                                                exportedFile
                                            )
                                            val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                                type = "application/pdf"
                                                putExtra(Intent.EXTRA_STREAM, shareUri)
                                                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                            }
                                            context.startActivity(Intent.createChooser(shareIntent, "Share Clean PDF"))
                                        }
                                    }) {
                                        Icon(Icons.Default.Download, contentDescription = "Export PDF", tint = SuccessGreen)
                                    }
                                }

                                // Open PDF File Button
                                IconButton(onClick = { pdfPickerLauncher.launch("application/pdf") }) {
                                    Icon(Icons.Default.UploadFile, contentDescription = "Upload PDF", tint = AccentBlue)
                                }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkSurface)
                        )
                    },
                    bottomBar = {
                        Surface(
                            color = DarkSurface,
                            tonalElevation = 2.dp,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(32.dp)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .padding(horizontal = 16.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = if (pageCount > 0) "Page ${currentPageIndex + 1} of $pageCount" else "Ready",
                                    fontSize = 11.sp,
                                    color = TextSecondary
                                )
                                Text(
                                    text = "Made by Gaurav",
                                    fontSize = 11.sp,
                                    color = TextSecondary,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }
                    }
                ) { paddingValues ->
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(paddingValues)
                    ) {
                        if (docId == null) {
                            // Empty State
                            Column(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .padding(32.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Surface(
                                    shape = RoundedCornerShape(16.dp),
                                    color = DarkSurface,
                                    modifier = Modifier.size(100.dp)
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        Icon(
                                            Icons.Default.PictureAsPdf,
                                            contentDescription = null,
                                            modifier = Modifier.size(56.dp),
                                            tint = AccentBlue
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(24.dp))

                                Text(
                                    text = "Edip PDF Studio",
                                    fontSize = 22.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )

                                Spacer(modifier = Modifier.height(8.dp))

                                Text(
                                    text = "Real PDF object manipulation on your phone.\n• Tap any text/line on page to edit directly\n• Toggle between Line Mode and Word Mode\n• Tap + to add new text elements\n• Tap ✏️ to search and pick text from list\n• Tap scanner icon to OCR scanned pages",
                                    fontSize = 14.sp,
                                    color = TextSecondary,
                                    lineHeight = 22.sp
                                )

                                Spacer(modifier = Modifier.height(30.dp))

                                Button(
                                    onClick = { pdfPickerLauncher.launch("application/pdf") },
                                    colors = ButtonDefaults.buttonColors(containerColor = AccentBlue),
                                    modifier = Modifier.height(48.dp)
                                ) {
                                    Icon(Icons.Default.FolderOpen, contentDescription = null)
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Open PDF to Edit", fontWeight = FontWeight.SemiBold)
                                }

                                Spacer(modifier = Modifier.height(28.dp))

                                Text(
                                    text = "Made by Gaurav",
                                    fontSize = 12.sp,
                                    color = TextSecondary,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        } else {
                            // Interactive Canvas View: 1-finger pan & tap, 2-finger zoom/pan
                            PdfCanvasView(
                                pageBitmap = pageBitmap,
                                pageInfo = pageInfo,
                                selectedSpan = selectedSpan,
                                dragOffset = dragOffset,
                                isDragMode = isDragMode,
                                isLineMode = isLineMode,
                                onSpanSelected = { span ->
                                    viewModel.selectSpan(span)
                                },
                                onDragDelta = { dx, dy ->
                                    viewModel.addDragDelta(dx, dy)
                                },
                                modifier = Modifier.fillMaxSize()
                            )

                            // Scanned Document Notification Pill
                            if (pageInfo?.text_blocks?.isEmpty() == true) {
                                Surface(
                                    modifier = Modifier
                                        .align(Alignment.TopCenter)
                                        .padding(top = 12.dp, start = 16.dp, end = 16.dp),
                                    shape = RoundedCornerShape(24.dp),
                                    color = DarkSurface.copy(alpha = 0.95f),
                                    border = BorderStroke(1.dp, WarningColor.copy(alpha = 0.6f)),
                                    shadowElevation = 6.dp
                                ) {
                                    Row(
                                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                                    ) {
                                        Icon(
                                            Icons.Default.DocumentScanner,
                                            contentDescription = null,
                                            tint = WarningColor,
                                            modifier = Modifier.size(20.dp)
                                        )
                                        Text(
                                            text = "Scanned document",
                                            fontSize = 12.sp,
                                            color = TextPrimary,
                                            fontWeight = FontWeight.Medium
                                        )
                                        Button(
                                            onClick = { viewModel.runOcr() },
                                            colors = ButtonDefaults.buttonColors(containerColor = AccentBlue),
                                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                                            modifier = Modifier.height(32.dp)
                                        ) {
                                            Text("Run OCR to Edit", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                        }
                                    }
                                }
                            }
                        }

                        // Text List Bottom Sheet (opens when ✏️ icon in top bar is tapped)
                        if (showTextListSheet && pageInfo != null) {
                            TextListBottomSheet(
                                pageInfo = pageInfo!!,
                                isLineMode = isLineMode,
                                onSpanSelected = { span ->
                                    viewModel.selectSpan(span)
                                    showTextListSheet = false
                                },
                                onDeleteSpan = { span ->
                                    viewModel.deleteSpan(span)
                                },
                                onRunOcr = {
                                    showTextListSheet = false
                                    viewModel.runOcr()
                                },
                                onDismiss = { showTextListSheet = false }
                            )
                        }

                        // Bottom Sheet Text Editor (appears automatically when any text is single-tapped or chosen from list)
                        if (selectedSpan != null) {
                            TextEditBottomSheet(
                                span = selectedSpan!!,
                                isDragMode = isDragMode,
                                onDragModeChange = { viewModel.setDragMode(it) },
                                onApplyEdit = { newText, fontName, fontSize, colorRgb ->
                                    viewModel.applyTextEdit(newText, fontName, fontSize, colorRgb)
                                },
                                onDeleteText = {
                                    viewModel.deleteSelectedText()
                                },
                                onDismiss = {
                                    viewModel.selectSpan(null)
                                }
                            )
                        }

                        // Dialog: Jump to Page
                        if (showPageJumpDialog) {
                            var targetPageInput by remember { mutableStateOf("${currentPageIndex + 1}") }
                            AlertDialog(
                                onDismissRequest = { showPageJumpDialog = false },
                                title = { Text("Jump to Page (1-$pageCount)") },
                                text = {
                                    OutlinedTextField(
                                        value = targetPageInput,
                                        onValueChange = { targetPageInput = it },
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                        singleLine = true,
                                        colors = OutlinedTextFieldDefaults.colors(
                                            focusedBorderColor = AccentBlue,
                                            unfocusedBorderColor = DarkSurfaceVariant,
                                            focusedTextColor = TextPrimary,
                                            unfocusedTextColor = TextPrimary
                                        )
                                    )
                                },
                                confirmButton = {
                                    Button(
                                        onClick = {
                                            val pNum = targetPageInput.toIntOrNull()
                                            if (pNum != null && pNum in 1..pageCount) {
                                                viewModel.changePage(pNum - 1)
                                            }
                                            showPageJumpDialog = false
                                        },
                                        colors = ButtonDefaults.buttonColors(containerColor = AccentBlue)
                                    ) {
                                        Text("Go")
                                    }
                                },
                                dismissButton = {
                                    TextButton(onClick = { showPageJumpDialog = false }) {
                                        Text("Cancel", color = TextSecondary)
                                    }
                                },
                                containerColor = DarkSurface
                            )
                        }

                        // Dialog: Add New Text to PDF
                        if (showAddTextDialog && pageInfo != null) {
                            var newTextVal by remember { mutableStateOf("") }
                            var fontSizeVal by remember { mutableFloatStateOf(14f) }
                            var fontNameVal by remember { mutableStateOf("helv") }
                            val colorOptions = listOf(
                                Pair(Color(0xFF000000), listOf(0f, 0f, 0f)),
                                Pair(Color(0xFF2563EB), listOf(0.145f, 0.388f, 0.921f)),
                                Pair(Color(0xFFDC2626), listOf(0.862f, 0.149f, 0.149f)),
                                Pair(Color(0xFF16A34A), listOf(0.086f, 0.639f, 0.290f))
                            )
                            var selectedColor by remember { mutableStateOf(colorOptions[0].second) }

                            AlertDialog(
                                onDismissRequest = { showAddTextDialog = false },
                                title = { Text("Add New Text to Page", color = AccentBlue, fontWeight = FontWeight.Bold) },
                                text = {
                                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                        OutlinedTextField(
                                            value = newTextVal,
                                            onValueChange = { newTextVal = it },
                                            placeholder = { Text("Type new text here...") },
                                            modifier = Modifier.fillMaxWidth(),
                                            colors = OutlinedTextFieldDefaults.colors(
                                                focusedBorderColor = AccentBlue,
                                                unfocusedBorderColor = DarkSurfaceVariant,
                                                focusedTextColor = TextPrimary,
                                                unfocusedTextColor = TextPrimary
                                            )
                                        )

                                        Row(
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            modifier = Modifier.fillMaxWidth(),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                                listOf("helv" to "Sans", "tiro" to "Serif", "cour" to "Mono").forEach { (code, label) ->
                                                    FilterChip(
                                                        selected = fontNameVal == code,
                                                        onClick = { fontNameVal = code },
                                                        label = { Text(label, fontSize = 11.sp) }
                                                    )
                                                }
                                            }
                                        }

                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            colorOptions.forEach { (c, rgb) ->
                                                val isSelected = selectedColor == rgb
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
                                                        .clickable { selectedColor = rgb }
                                                )
                                            }
                                        }
                                    }
                                },
                                confirmButton = {
                                    Button(
                                        onClick = {
                                            if (newTextVal.isNotBlank() && pageInfo != null) {
                                                val posX = (pageInfo!!.width / 4f).coerceAtLeast(36f)
                                                val posY = (pageInfo!!.height / 3f).coerceAtLeast(36f)
                                                viewModel.addNewText(
                                                    text = newTextVal,
                                                    x = posX,
                                                    y = posY,
                                                    fontName = fontNameVal,
                                                    fontSize = fontSizeVal,
                                                    colorRgb = selectedColor
                                                )
                                            }
                                            showAddTextDialog = false
                                        },
                                        colors = ButtonDefaults.buttonColors(containerColor = AccentBlue)
                                    ) {
                                        Text("Add Text")
                                    }
                                },
                                dismissButton = {
                                    TextButton(onClick = { showAddTextDialog = false }) {
                                        Text("Cancel", color = TextSecondary)
                                    }
                                },
                                containerColor = DarkSurface
                            )
                        }

                        // Loading Progress Indicator
                        if (isLoading) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .background(DarkBackground.copy(alpha = 0.6f)),
                                contentAlignment = Alignment.Center
                            ) {
                                CircularProgressIndicator(color = AccentBlue)
                            }
                        }
                    }
                }
            }
        }
    }
}

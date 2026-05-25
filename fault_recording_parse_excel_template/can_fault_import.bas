' Import CAN fault recording CSV into sheet Raw (Import CSV button only).
' Excel 2016 / 2019 / 2021 / Microsoft 365 (Windows).
Option Explicit
Private Const RAW_SHEET As String = "Raw"
Private Const PARSED_SHEET As String = "Parsed"
Private Const LOG_SHEET As String = "ImportLog"
Private Const MAX_RAW_ROW As Long = 3201
Private Const MIN_EXCEL_VERSION As Double = 16#
Private Const PROGRESS_WIDTH As Long = 40
Private Const CHART_LEFT As Double = 280
Private Const CHART_WIDTH As Double = 480
Private Const CHART_HEIGHT As Double = 145
Private Const CHART_VGAP As Double = 12
Private Const PLOT_LAST_ROW As Long = 502
Private Const PLOT_MAX_SAMPLES As Long = 500
Private Const NUM_CAN_IDS As Long = 6
Private Const PROGRESS_ROW_INTERVAL As Long = 500
Private gImportedRows As Long
Public Function EnsureExcelVersion() As Boolean
    Dim ver As Double
    ver = Val(Application.Version)
    If ver < MIN_EXCEL_VERSION Then
        MsgBox "Requires Excel 2016 or later (2016 / 2019 / 2021 / Microsoft 365).", _
            vbCritical, "CAN Fault Template"
        EnsureExcelVersion = False
        Exit Function
    End If
    EnsureExcelVersion = True
End Function
Public Sub ProtectRawSheet()
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(RAW_SHEET)
    On Error Resume Next
    ws.Unprotect Password:=""
    ws.Unprotect
    On Error GoTo 0
    ws.Protect Password:="", UserInterfaceOnly:=True
End Sub
Public Sub PromptImportIfEmpty()
    Dim ws As Worksheet
    Dim caption As String
    Set ws = ThisWorkbook.Worksheets(RAW_SHEET)
    If WorksheetFunction.CountA(ws.Range("A2:I" & MAX_RAW_ROW)) = 0 Then
        caption = TemplateVersionCaption()
        If Len(caption) > 0 Then
            caption = "CAN Fault Template · " & caption
        Else
            caption = "CAN Fault Template"
        End If
        MsgBox "No data loaded. Click Import CSV... to load a recording file.", _
            vbInformation, caption
    End If
End Sub
Private Sub UpdateImportProgress(ByVal pct As Double, ByVal msg As String)
    Dim filled As Long
    Dim bar As String
    If pct < 0# Then pct = 0#
    If pct > 1# Then pct = 1#
    filled = CLng(pct * PROGRESS_WIDTH)
    bar = "[" & String$(filled, "=") & String$(PROGRESS_WIDTH - filled, ".") & "]"
    Application.StatusBar = msg & "  " & Format(pct, "0%") & "  " & bar
    DoEvents
End Sub
Public Sub ImportCanFaultCsv()
    Dim fd As FileDialog
    Dim path As String
    If Not EnsureExcelVersion() Then Exit Sub
    Set fd = Application.FileDialog(msoFileDialogFilePicker)
    fd.Title = "Select CAN fault recording CSV"
    fd.Filters.Clear
    fd.Filters.Add "CSV files", "*.csv"
    fd.AllowMultiSelect = False
    If fd.Show <> -1 Then Exit Sub
    path = fd.SelectedItems(1)
    Call ImportCanFaultCsvFromPath(path)
End Sub
Public Sub ImportCanFaultCsvFromPath(ByVal path As String)
    Dim wsRaw As Worksheet
    Dim imported As Long
    Dim errNum As Long
    Dim errDesc As String
    Dim stepName As String
    Dim oldCalc As XlCalculation
    Dim oldScreenUpdating As Boolean
    Set wsRaw = ThisWorkbook.Worksheets(RAW_SHEET)
    oldCalc = Application.Calculation
    oldScreenUpdating = Application.ScreenUpdating
    Application.Calculation = xlCalculationManual
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.DisplayStatusBar = True
    Application.Cursor = xlWait
    On Error GoTo CleanFail
    Call UpdateImportProgress(0#, "Starting import...")
    stepName = "unlock Raw sheet"
    Call UnprotectRaw(wsRaw)
    stepName = "clear sheets"
    Call UpdateImportProgress(0.02, "Clearing old data...")
    wsRaw.Range("A2:I" & MAX_RAW_ROW).ClearContents
    ThisWorkbook.Worksheets(PARSED_SHEET).Range("A2:O" & MAX_RAW_ROW).ClearContents
    Call ClearAllPlotDataRanges
    stepName = "read CSV file"
    imported = ImportCsvToRaw(wsRaw, path)
    If imported = 0 Then
        Call RestoreUiAfterImport(oldCalc, oldScreenUpdating)
        Call WriteImportLog("read CSV file", 0, "No data rows found in CSV", path, "ImportCanFaultCsvFromPath")
        MsgBox "No data rows found in:" & vbCrLf & path, vbExclamation, "Import CSV"
        GoTo CleanExit
    End If
    gImportedRows = imported
    stepName = "fill Parsed and Plot sheets"
    Call FillParsedAndPlotsFromRaw(imported)
    stepName = "update charts"
    Call RecalculatePlotSheetsOnly
    stepName = "protect Raw"
    Call UpdateImportProgress(0.98, "Finishing...")
    Call ProtectRawSheet
    Call UpdateImportProgress(1#, "Done")
    Call RestoreUiAfterImport(oldCalc, oldScreenUpdating)
    Call ShowImportSuccessMessage(imported, path)
    GoTo CleanExit
CleanFail:
    Dim errSource As String
    errNum = Err.Number
    errDesc = Trim$(Err.Description)
    errSource = Trim$(Err.Source)
    If Len(errDesc) = 0 Then errDesc = errSource
    If Len(errDesc) = 0 Then errDesc = "(no description)"
    If Len(stepName) = 0 Then stepName = "(unknown step)"
    On Error Resume Next
    Application.Calculation = oldCalc
    Application.StatusBar = False
    Application.Cursor = xlDefault
    Application.ScreenUpdating = True
    Call WriteImportLog(stepName, errNum, errDesc, path, errSource)
    MsgBox "Import failed at step: " & stepName & vbCrLf & _
        "Error " & CStr(errNum) & ": " & errDesc & vbCrLf & vbCrLf & _
        "Details: open sheet ImportLog" & vbCrLf & _
        "File: " & path, vbCritical, "Import CSV"
CleanExit:
    On Error Resume Next
    Application.Calculation = oldCalc
    Application.StatusBar = False
    Application.Cursor = xlDefault
    Call ProtectRawSheet
    Application.EnableEvents = True
    Application.ScreenUpdating = oldScreenUpdating
End Sub
Public Sub RebuildAllPlotCharts()
    Dim ws As Worksheet
    For Each ws In ThisWorkbook.Worksheets
        If Left$(ws.Name, 5) = "Plot_" Then
            Call RebuildPlotSheetCharts(ws)
        End If
    Next ws
End Sub
Private Function NormalizeCanId(ByVal s As String) As String
    Dim t As String
    t = UCase$(Trim$(s))
    If Left$(t, 1) = "'" Then t = Mid$(t, 2)
    NormalizeCanId = t
End Function
Private Function CanIdToIndex(ByVal canId As String) As Long
    Select Case NormalizeCanId(canId)
        Case "0X1A960004": CanIdToIndex = 0
        Case "0X1A970004": CanIdToIndex = 1
        Case "0X1A980004": CanIdToIndex = 2
        Case "0X1A990004": CanIdToIndex = 3
        Case "0X1A9A0004": CanIdToIndex = 4
        Case "0X1A9B0004": CanIdToIndex = 5
        Case Else: CanIdToIndex = -1
    End Select
End Function
Private Function PlotSheetNameByIndex(ByVal idx As Long) As String
    Select Case idx
        Case 0: PlotSheetNameByIndex = "Plot_1A960004"
        Case 1: PlotSheetNameByIndex = "Plot_1A970004"
        Case 2: PlotSheetNameByIndex = "Plot_1A980004"
        Case 3: PlotSheetNameByIndex = "Plot_1A990004"
        Case 4: PlotSheetNameByIndex = "Plot_1A9A0004"
        Case 5: PlotSheetNameByIndex = "Plot_1A9B0004"
    End Select
End Function
Private Sub ClearAllPlotDataRanges()
    Dim i As Long
    Dim ws As Worksheet
    For i = 0 To NUM_CAN_IDS - 1
        Set ws = ThisWorkbook.Worksheets(PlotSheetNameByIndex(i))
        ws.Range("A3:E" & CStr(PLOT_LAST_ROW)).ClearContents
    Next i
End Sub
Private Sub FillParsedAndPlotsFromRaw(ByVal imported As Long)
    Dim wsRaw As Worksheet
    Dim wsParsed As Worksheet
    Dim rawArr As Variant
    Dim parsedArr() As Variant
    Dim plotAll(0 To 5, 1 To PLOT_MAX_SAMPLES, 1 To 5) As Variant
    Dim plotCount(0 To 5) As Long
    Dim seqCount(0 To 5) As Long
    Dim r As Long
    Dim canIdText As String
    Dim canIndex As Long
    Dim b0 As Long
    Dim b1 As Long
    Dim b2 As Long
    Dim b3 As Long
    Dim b4 As Long
    Dim b5 As Long
    Dim b6 As Long
    Dim b7 As Long
    Dim sampleIdx As Long
    Dim wsPlot As Worksheet
    Dim i As Long
    Dim j As Long
    Set wsRaw = ThisWorkbook.Worksheets(RAW_SHEET)
    Set wsParsed = ThisWorkbook.Worksheets(PARSED_SHEET)
    rawArr = wsRaw.Range("A2:I" & CStr(imported + 1)).Value2
    rawArr = NormalizeRawArray(rawArr, imported)
    ReDim parsedArr(1 To imported, 1 To 15)
    For i = 0 To 5
        seqCount(i) = 0
        plotCount(i) = 0
    Next i
    For r = 1 To imported
        If (r Mod PROGRESS_ROW_INTERVAL) = 0 Or r = 1 Or r = imported Then
            Call UpdateImportProgress(0.45 + (CDbl(r - 1) / CDbl(imported)) * 0.3, _
                "Parsing row " & CStr(r) & "/" & CStr(imported) & "...")
        End If
        canIdText = NormalizeCanId(CStr(rawArr(r, 1)))
        b0 = ParseHexByte(CStr(rawArr(r, 2)))
        b1 = ParseHexByte(CStr(rawArr(r, 3)))
        b2 = ParseHexByte(CStr(rawArr(r, 4)))
        b3 = ParseHexByte(CStr(rawArr(r, 5)))
        b4 = ParseHexByte(CStr(rawArr(r, 6)))
        b5 = ParseHexByte(CStr(rawArr(r, 7)))
        b6 = ParseHexByte(CStr(rawArr(r, 8)))
        b7 = ParseHexByte(CStr(rawArr(r, 9)))
        parsedArr(r, 1) = r
        parsedArr(r, 2) = CStr(rawArr(r, 1))
        canIndex = CanIdToIndex(canIdText)
        If canIndex >= 0 Then
            seqCount(canIndex) = seqCount(canIndex) + 1
            parsedArr(r, 3) = seqCount(canIndex)
            If plotCount(canIndex) < PLOT_MAX_SAMPLES Then
                plotCount(canIndex) = plotCount(canIndex) + 1
                sampleIdx = plotCount(canIndex)
                plotAll(canIndex, sampleIdx, 1) = sampleIdx
                plotAll(canIndex, sampleIdx, 2) = Int16FromBytes(b0, b1)
                plotAll(canIndex, sampleIdx, 3) = Int16FromBytes(b2, b3)
                plotAll(canIndex, sampleIdx, 4) = Int16FromBytes(b4, b5)
                plotAll(canIndex, sampleIdx, 5) = Int16FromBytes(b6, b7)
            End If
        Else
            parsedArr(r, 3) = ""
        End If
        parsedArr(r, 4) = b0
        parsedArr(r, 5) = b1
        parsedArr(r, 6) = b2
        parsedArr(r, 7) = b3
        parsedArr(r, 8) = b4
        parsedArr(r, 9) = b5
        parsedArr(r, 10) = b6
        parsedArr(r, 11) = b7
        parsedArr(r, 12) = Int16FromBytes(b0, b1)
        parsedArr(r, 13) = Int16FromBytes(b2, b3)
        parsedArr(r, 14) = Int16FromBytes(b4, b5)
        parsedArr(r, 15) = Int16FromBytes(b6, b7)
    Next r
    wsParsed.Range("A2").Resize(imported, 15).Value = parsedArr
    Call UpdateImportProgress(0.78, "Writing Plot sheets...")
    For i = 0 To NUM_CAN_IDS - 1
        If plotCount(i) > 0 Then
            Set wsPlot = ThisWorkbook.Worksheets(PlotSheetNameByIndex(i))
            wsPlot.Range("A3").Resize(plotCount(i), 5).Value = _
                ExtractPlotSlice(plotAll, i, plotCount(i))
        End If
    Next i
End Sub
Private Function ExtractPlotSlice(ByRef plotAll() As Variant, ByVal canIndex As Long, _
    ByVal nRows As Long) As Variant
    Dim outArr() As Variant
    Dim r As Long
    Dim c As Long
    ReDim outArr(1 To nRows, 1 To 5)
    For r = 1 To nRows
        For c = 1 To 5
            outArr(r, c) = plotAll(canIndex, r, c)
        Next c
    Next r
    ExtractPlotSlice = outArr
End Function
Private Sub RebuildPlotSheetCharts(ByVal ws As Worksheet)
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow < 3 Then Exit Sub
    If lastRow > PLOT_LAST_ROW Then lastRow = PLOT_LAST_ROW
    If ws.ChartObjects.Count = 4 Then
        Call UpdatePlotSheetCharts(ws, lastRow)
    Else
        Call CreatePlotSheetCharts(ws, lastRow)
    End If
End Sub
Private Sub UpdatePlotSheetCharts(ByVal ws As Worksheet, ByVal lastRow As Long)
    Dim co As ChartObject
    Dim ch As Chart
    Dim i As Long
    Dim chCol As Long
    Dim chName As String
    Dim rngX As Range
    Dim rngY As Range
    i = 0
    For Each co In ws.ChartObjects
        If i > 3 Then Exit For
        Select Case i
            Case 0: chName = "b0b1": chCol = 2
            Case 1: chName = "b2b3": chCol = 3
            Case 2: chName = "b4b5": chCol = 4
            Case 3: chName = "b6b7": chCol = 5
        End Select
        Set rngX = ws.Range("A3:A" & CStr(lastRow))
        Set rngY = ws.Range(ws.Cells(3, chCol), ws.Cells(lastRow, chCol))
        Set ch = co.Chart
        Do While ch.SeriesCollection.Count > 0
            ch.SeriesCollection(1).Delete
        Loop
        ch.SeriesCollection.Add Source:=rngY
        With ch.SeriesCollection(1)
            .XValues = rngX
            .Name = chName
        End With
        i = i + 1
    Next co
End Sub
Private Sub CreatePlotSheetCharts(ByVal ws As Worksheet, ByVal lastRow As Long)
    Dim co As ChartObject
    Dim ch As Chart
    Dim i As Long
    Dim topPos As Double
    Dim canShort As String
    Dim rngX As Range
    Dim rngY As Range
    Dim chName As String
    Dim chCol As Long
    On Error GoTo ChartFail
    canShort = Replace(CStr(ws.Range("B1").Value2), "0x", "")
    For Each co In ws.ChartObjects
        co.Delete
    Next co
    topPos = 12
    For i = 0 To 3
        Select Case i
            Case 0: chName = "b0b1": chCol = 2
            Case 1: chName = "b2b3": chCol = 3
            Case 2: chName = "b4b5": chCol = 4
            Case 3: chName = "b6b7": chCol = 5
        End Select
        Set rngX = ws.Range("A3:A" & CStr(lastRow))
        Set rngY = ws.Range(ws.Cells(3, chCol), ws.Cells(lastRow, chCol))
        Set co = ws.ChartObjects.Add( _
            Left:=CHART_LEFT, Top:=topPos, Width:=CHART_WIDTH, Height:=CHART_HEIGHT)
        Set ch = co.Chart
        ch.ChartType = xlLine
        Do While ch.SeriesCollection.Count > 0
            ch.SeriesCollection(1).Delete
        Loop
        ch.SeriesCollection.Add Source:=rngY
        With ch.SeriesCollection(1)
            .XValues = rngX
            .Name = chName
        End With
        ch.HasTitle = True
        ch.ChartTitle.Text = canShort & " - " & chName
        ch.HasLegend = True
        ch.Legend.Position = xlLegendPositionRight
        With ch.Axes(xlCategory)
            .HasTitle = True
            .AxisTitle.Text = "sample"
            .TickLabelPosition = xlTickLabelPositionLow
            .AxisBetweenCategories = False
        End With
        With ch.Axes(xlValue)
            .HasTitle = True
            .AxisTitle.Text = "int16"
            .Crosses = xlMinimum
        End With
        topPos = topPos + CHART_HEIGHT + CHART_VGAP
    Next i
    Exit Sub
ChartFail:
    Err.Raise Err.Number, "CreatePlotSheetCharts(" & ws.Name & ")", Err.Description
End Sub
Private Sub RecalculatePlotSheetsOnly()
    Dim names As Variant
    Dim i As Long
    Dim pct As Double
    Dim ws As Worksheet
    names = Array("Plot_1A960004", "Plot_1A970004", "Plot_1A980004", _
        "Plot_1A990004", "Plot_1A9A0004", "Plot_1A9B0004")
    For i = LBound(names) To UBound(names)
        pct = 0.8 + (CDbl(i - LBound(names) + 1) / (UBound(names) - LBound(names) + 1)) * 0.17
        Call UpdateImportProgress(pct, "Updating charts " & CStr(i - LBound(names) + 1) & "/6...")
        Set ws = ThisWorkbook.Worksheets(CStr(names(i)))
        Call RebuildPlotSheetCharts(ws)
    Next i
End Sub
Private Function Int16FromBytes(ByVal hi As Long, ByVal lo As Long) As Long
    Dim v As Long
    v = hi * 256 + lo
    If v >= 32768 Then v = v - 65536
    Int16FromBytes = v
End Function
Private Function NormalizeRawArray(ByVal rawArr As Variant, ByVal imported As Long) As Variant
    Dim outArr() As Variant
    Dim r As Long
    Dim c As Long
    Dim probe As Variant
    If imported <= 0 Then
        NormalizeRawArray = rawArr
        Exit Function
    End If
    On Error Resume Next
    probe = rawArr(1, 1)
    If Err.Number = 0 Then
        On Error GoTo 0
        NormalizeRawArray = rawArr
        Exit Function
    End If
    Err.Clear
    On Error GoTo 0
    ReDim outArr(1 To imported, 1 To 9)
    If imported = 1 Then
        For c = 1 To 9
            outArr(1, c) = rawArr(c)
        Next c
    Else
        For r = 1 To imported
            For c = 1 To 9
                outArr(r, c) = rawArr(r, c)
            Next c
        Next r
    End If
    NormalizeRawArray = outArr
End Function
Private Function ParseHexByte(ByVal s As String) As Long
    Dim t As String
    t = UCase$(Trim$(s))
    If Left$(t, 1) = "'" Then t = Mid$(t, 2)
    If Left$(t, 2) = "0X" Then t = Mid$(t, 3)
    ParseHexByte = CLng("&H" & t)
End Function
Public Sub ShowLastImportLog()
    On Error Resume Next
    ThisWorkbook.Worksheets(LOG_SHEET).Activate
    On Error GoTo 0
End Sub
Private Sub RestoreUiAfterImport(ByVal oldCalc As XlCalculation, ByVal oldScreenUpdating As Boolean)
    On Error Resume Next
    Application.Calculation = oldCalc
    Application.StatusBar = False
    Application.Cursor = xlDefault
    Application.ScreenUpdating = oldScreenUpdating
    On Error GoTo 0
End Sub

Private Function CountDistinctCanIdsInRaw(ByVal imported As Long) As Long
    Dim ws As Worksheet
    Dim rawArr As Variant
    Dim seen As Object
    Dim i As Long
    Dim idText As String

    If imported <= 0 Then
        CountDistinctCanIdsInRaw = 0
        Exit Function
    End If

    Set ws = ThisWorkbook.Worksheets(RAW_SHEET)
    rawArr = ws.Range("A2:A" & CStr(imported + 1)).Value2
    rawArr = NormalizeRawArray(rawArr, imported)
    Set seen = CreateObject("Scripting.Dictionary")
    seen.CompareMode = 1

    For i = 1 To imported
        idText = NormalizeCanId(CStr(rawArr(i, 1)))
        If Len(idText) > 0 Then
            If Not seen.Exists(idText) Then seen.Add idText, True
        End If
    Next i
    CountDistinctCanIdsInRaw = seen.Count
End Function

Private Sub ShowImportSuccessMessage(ByVal imported As Long, ByVal path As String)
    Dim canIdCount As Long
    Dim msg As String
    Dim caption As String

    canIdCount = CountDistinctCanIdsInRaw(imported)
    msg = "Import completed successfully." & vbCrLf & vbCrLf & _
        "Imported rows: " & CStr(imported) & vbCrLf & _
        "Distinct CAN IDs: " & CStr(canIdCount) & vbCrLf & vbCrLf & _
        "Source file:" & vbCrLf & path
    caption = TemplateVersionCaption()
    If Len(caption) > 0 Then
        caption = "Import CSV · " & caption
    Else
        caption = "Import CSV"
    End If
    MsgBox msg, vbInformation, caption
End Sub

Private Function TemplateVersionCaption() As String
    Dim ver As String
    Dim relDate As String
    On Error GoTo Fail
    ver = Trim$(CStr(ThisWorkbook.Names("TemplateVersion").RefersToRange.Value2))
    relDate = Trim$(CStr(ThisWorkbook.Names("TemplateReleaseDate").RefersToRange.Value2))
    If Len(ver) = 0 Then GoTo Fail
    If Left$(ver, 1) <> "v" And Left$(ver, 1) <> "V" Then ver = "v" & ver
    If Len(relDate) > 0 Then
        TemplateVersionCaption = ver & " · " & relDate
    Else
        TemplateVersionCaption = ver
    End If
    Exit Function
Fail:
    TemplateVersionCaption = ""
End Function

Private Function ImportLogNextRow(ByVal ws As Worksheet) As Long
    Dim lastRow As Long
    Dim cell2a As String

    cell2a = Trim$(CStr(ws.Cells(2, 1).Value2))
    If Len(cell2a) = 0 Then
        ImportLogNextRow = 2
        Exit Function
    End If
    If InStr(1, cell2a, "empty until", vbTextCompare) > 0 Then
        ws.Range("A2:F2").ClearContents
        ImportLogNextRow = 2
        Exit Function
    End If
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow < 1 Then lastRow = 1
    ImportLogNextRow = lastRow + 1
    If ImportLogNextRow < 2 Then ImportLogNextRow = 2
End Function

Private Sub WriteImportLog(ByVal stepName As String, ByVal errNum As Long, _
    ByVal errDesc As String, ByVal path As String, Optional ByVal errSource As String = "")
    Dim ws As Worksheet
    Dim nextRow As Long
    Dim src As String

    On Error GoTo LogWriteFail
    Set ws = ThisWorkbook.Worksheets(LOG_SHEET)
    On Error Resume Next
    ws.Unprotect Password:=""
    ws.Unprotect
    On Error GoTo LogWriteFail

    nextRow = ImportLogNextRow(ws)
    src = errSource
    If Len(src) = 0 Then src = "ImportCanFaultCsvFromPath"

    ws.Cells(nextRow, 1).Value = Now
    ws.Cells(nextRow, 2).Value = stepName
    ws.Cells(nextRow, 3).Value = errNum
    ws.Cells(nextRow, 4).Value = errDesc
    ws.Cells(nextRow, 5).Value = path
    ws.Cells(nextRow, 6).Value = src
    ws.Activate
    ws.Cells(nextRow, 1).Select
    Exit Sub

LogWriteFail:
    On Error Resume Next
    MsgBox "Could not write ImportLog sheet." & vbCrLf & _
        "Step: " & stepName & vbCrLf & _
        "Error " & CStr(errNum) & ": " & errDesc, vbExclamation, "Import CSV"
End Sub
Private Sub UnprotectRaw(ByVal ws As Worksheet)
    On Error Resume Next
    ws.Unprotect Password:=""
    ws.Unprotect
    On Error GoTo 0
End Sub
Private Function ImportCsvToRaw(ByVal ws As Worksheet, ByVal path As String) As Long
    Dim n As Long
    On Error GoTo TryLineInput
    n = ImportCsvAdodbBulk(ws, path)
    If n > 0 Then
        ImportCsvToRaw = n
        Exit Function
    End If
TryLineInput:
    Err.Clear
    On Error GoTo 0
    ImportCsvToRaw = ImportCsvLineInputBulk(ws, path)
End Function
Private Function CsvPartsToRawRow(ByRef parts() As String, ByRef rowOut() As Variant) As Boolean
    Dim firstCell As String
    If UBound(parts) < 8 Then Exit Function
    firstCell = Trim$(CStr(parts(0)))
    If LCase$(Left$(firstCell, 6)) = "can_id" Then Exit Function
    rowOut(1) = "'" & Trim$(CStr(parts(0)))
    rowOut(2) = "'" & Trim$(CStr(parts(1)))
    rowOut(3) = "'" & Trim$(CStr(parts(2)))
    rowOut(4) = "'" & Trim$(CStr(parts(3)))
    rowOut(5) = "'" & Trim$(CStr(parts(4)))
    rowOut(6) = "'" & Trim$(CStr(parts(5)))
    rowOut(7) = "'" & Trim$(CStr(parts(6)))
    rowOut(8) = "'" & Trim$(CStr(parts(7)))
    rowOut(9) = "'" & Trim$(CStr(parts(8)))
    CsvPartsToRawRow = True
End Function
Private Function CountCsvDataRows(ByRef lines() As String) As Long
    Dim i As Long
    Dim line As String
    Dim parts() As String
    Dim firstCell As String
    Dim cnt As Long
    cnt = 0
    For i = LBound(lines) To UBound(lines)
        line = Trim$(CStr(lines(i)))
        If Len(line) = 0 Then GoTo NextLine
        If Left$(line, 1) = "#" Then GoTo NextLine
        parts = Split(line, ",")
        If UBound(parts) < 8 Then GoTo NextLine
        firstCell = Trim$(CStr(parts(0)))
        If LCase$(Left$(firstCell, 6)) = "can_id" Then GoTo NextLine
        cnt = cnt + 1
        If cnt >= MAX_RAW_ROW - 1 Then Exit For
NextLine:
    Next i
    CountCsvDataRows = cnt
End Function
Private Function ImportCsvAdodbBulk(ByVal ws As Worksheet, ByVal path As String) As Long
    Dim stream As Object
    Dim content As String
    Dim lines() As String
    Dim data() As Variant
    Dim rowBuf(1 To 9) As Variant
    Dim parts() As String
    Dim line As String
    Dim i As Long
    Dim imported As Long
    Dim total As Long
    Dim rowIdx As Long
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.LoadFromFile path
    content = stream.ReadText(-1)
    stream.Close
    content = Replace(content, vbCrLf, vbLf)
    content = Replace(content, vbCr, vbLf)
    lines = Split(content, vbLf)
    total = UBound(lines) - LBound(lines) + 1
    imported = CountCsvDataRows(lines)
    If imported = 0 Then
        ImportCsvAdodbBulk = 0
        Exit Function
    End If
    ReDim data(1 To imported, 1 To 9)
    rowIdx = 0
    For i = LBound(lines) To UBound(lines)
        line = Trim$(CStr(lines(i)))
        If Len(line) = 0 Then GoTo NextLine
        If Left$(line, 1) = "#" Then GoTo NextLine
        parts = Split(line, ",")
        If CsvPartsToRawRow(parts, rowBuf) Then
            rowIdx = rowIdx + 1
            data(rowIdx, 1) = rowBuf(1)
            data(rowIdx, 2) = rowBuf(2)
            data(rowIdx, 3) = rowBuf(3)
            data(rowIdx, 4) = rowBuf(4)
            data(rowIdx, 5) = rowBuf(5)
            data(rowIdx, 6) = rowBuf(6)
            data(rowIdx, 7) = rowBuf(7)
            data(rowIdx, 8) = rowBuf(8)
            data(rowIdx, 9) = rowBuf(9)
            If (rowIdx Mod PROGRESS_ROW_INTERVAL) = 0 Then
                Call UpdateImportProgress(0.05 + (CDbl(rowIdx) / CDbl(imported)) * 0.38, _
                    "Reading CSV " & CStr(rowIdx) & "/" & CStr(imported) & "...")
            End If
            If rowIdx >= imported Then Exit For
        End If
NextLine:
    Next i
    ws.Range("A2").Resize(imported, 9).Value = data
    Call UpdateImportProgress(0.43, "CSV read complete")
    ImportCsvAdodbBulk = imported
End Function
Private Function ImportCsvLineInputBulk(ByVal ws As Worksheet, ByVal path As String) As Long
    Dim fn As Integer
    Dim line As String
    Dim parts() As String
    Dim data() As Variant
    Dim rowBuf(1 To 9) As Variant
    Dim rowIdx As Long
    Dim capacity As Long
    fn = FreeFile
    capacity = 1024
    ReDim data(1 To capacity, 1 To 9)
    rowIdx = 0
    Open path For Input As #fn
    Do While Not EOF(fn)
        Line Input #fn, line
        line = Trim$(line)
        If Len(line) = 0 Then GoTo ContinueLoop
        If Left$(line, 1) = "#" Then GoTo ContinueLoop
        parts = Split(line, ",")
        If CsvPartsToRawRow(parts, rowBuf) Then
            rowIdx = rowIdx + 1
            If rowIdx > capacity Then
                capacity = capacity + 1024
                ReDim Preserve data(1 To capacity, 1 To 9)
            End If
            data(rowIdx, 1) = rowBuf(1)
            data(rowIdx, 2) = rowBuf(2)
            data(rowIdx, 3) = rowBuf(3)
            data(rowIdx, 4) = rowBuf(4)
            data(rowIdx, 5) = rowBuf(5)
            data(rowIdx, 6) = rowBuf(6)
            data(rowIdx, 7) = rowBuf(7)
            data(rowIdx, 8) = rowBuf(8)
            data(rowIdx, 9) = rowBuf(9)
            If (rowIdx Mod PROGRESS_ROW_INTERVAL) = 0 Then
                Call UpdateImportProgress(0.05 + (CDbl(rowIdx) / 3200#) * 0.38, _
                    "Reading CSV " & CStr(rowIdx) & " rows...")
            End If
            If rowIdx >= MAX_RAW_ROW - 1 Then Exit Do
        End If
ContinueLoop:
    Loop
    Close #fn
    If rowIdx = 0 Then
        ImportCsvLineInputBulk = 0
        Exit Function
    End If
    If rowIdx < capacity Then ReDim Preserve data(1 To rowIdx, 1 To 9)
    ws.Range("A2").Resize(rowIdx, 9).Value = data
    Call UpdateImportProgress(0.43, "CSV read complete")
    ImportCsvLineInputBulk = rowIdx
End Function

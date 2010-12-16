"""
Processes data from ExtractLines and a test coverage output to
form a report xml document.

The tool can optionally process the log files from the previous 'n'
runs to include historical progress.
"""

from xml.dom.minidom import parse
from xml.sax.saxutils import escape
from syntaxhighlight import LuaHTMLLineOutput

# optionally use GChartWrapper if it exists
renderCharts = True
try:
    import GChartWrapper
except ImportError:
    renderCharts = False

import sys
import os.path
import time
import math
import StringIO

from optparse import OptionParser

startTime = time.clock()

optParser = OptionParser(usage = """
    lcovtools-makereport.py [options] <linesfile> <resultsfile> <reportfile> [previous logs]

    NOTE: You must specify previous log files in chronological order going backwards.  The
    previous log files should be report files output by this script. """)

optParser.add_option("-s", "--simple-code", action="store_true", dest="noSyntaxHighlighting", help="Do not syntax highlight the Lua in the report file")
optParser.add_option("-o", "--output-stdout", action="store_true", dest="outputToStdout", help="Do not syntax highlight the Lua in the report file")
optParser.add_option("-g", "--graph", action="store_true", dest="showGraph", help="Show a graph of the history of coverage (requires GChartWrapper)")
optParser.add_option("-e", "--header-only", action="store_true", dest="headersOnly", help="Only show the summary information")
optParser.add_option("-b", "--base", dest="base", help="Document me please!")
optParser.add_option("-r", "--summary-report", dest="summary", help="Generate a small summary report, useful as historical data")

(options, args) = optParser.parse_args()

requiredArgs = 3

if options.outputToStdout:
    requiredArgs = 2
    reportFile = sys.stdout
else:
    reportFile = open(args[2], "wt")

if options.showGraph and not renderCharts:
    print "Unable to find GChart, graphing disabled"
    options.showGraph = False

if len(args) < requiredArgs:
    optParser.print_help()
    sys.exit(-1)

validLines = parse(args[0])
coverageResults = parse(args[1])

history = []

for x in args[requiredArgs:]:
    print ("Using history from: " + x)
    history.append(parse(x))

linesRoot = validLines.getElementsByTagName("validLines")[0]
resultsRoot = coverageResults.getElementsByTagName("lcovtools")[0]

reportFile.write('<?xml version="1.0" encoding="utf-8"?>')
reportFile.write('<?xml-stylesheet type="text/xsl" href="report.xsl"?>')
reportFile.write('<!DOCTYPE xsl:stylesheet [')
reportFile.write('<!ENTITY nbsp "&#160;">')
reportFile.write(']>')
reportFile.write('<CoverageReport>')

totalLines = 0
totalValid = 0
totalVisited = 0

def escape_anchor(str):
    return str.replace("/", "_").replace("\\", "_").replace(".", "_")

def myescape(str):
    return escape(str).replace(' ', '&nbsp;').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')

for fileNode in linesRoot.getElementsByTagName("file"):
    validLines = set()

    for lineNode in fileNode.getElementsByTagName("l"):
        validLines.add(int(lineNode.getAttribute("no")))

    # Find results for this file
    resultsNode = None

    for resultFileNode in resultsRoot.getElementsByTagName("file"):
        if os.path.normcase(os.path.abspath(os.path.join(options.base, resultFileNode.getAttribute("name")))) == os.path.normcase(os.path.abspath(fileNode.getAttribute("name"))):
            resultsNode = resultFileNode

    if not resultsNode:
        reportFile.write(" <File name=\"%s\" missingResults=\"yes\" anchor=\"%s\"/>" % (fileNode.getAttribute("name"), escape_anchor(fileNode.getAttribute("name"))))
        
        srcfile = open(fileNode.getAttribute("name"), "rt")
        srccode = srcfile.read()
        srcfile.close()
        
        totalLines += len(srccode.split())
        totalValid += len(validLines)
    else:
        reportFile.write(" <File name=\"%s\" anchor=\"%s\">" % (fileNode.getAttribute("name"), escape_anchor(fileNode.getAttribute("name"))))

        srcfile = open(fileNode.getAttribute("name"), "rt")
        srccode = srcfile.read()
        srclines = []

        if options.noSyntaxHighlighting:
            srclines = [myescape(x) for x in srccode.splitlines()]
        else:
            for line in LuaHTMLLineOutput(srccode):
                srclines.append(line)

        srcline = 0

        validCount = 0
        visitedCount = 0
        
        filereport = StringIO.StringIO()

        for lineno in range(0, len(srclines)):

            valid = (lineno+1) in validLines
            visited = False

            if valid:
                validCount += 1

            if resultsNode:
                for linevisited in resultsNode.getElementsByTagName("line"):
                    if int(linevisited.getAttribute("number")) == lineno+1:
                        visited = True

            if visited:
                visitedCount += 1

            if not options.headersOnly:
                if len(srclines[lineno]):
                    filereport.write("  <Line no=\"%d\" valid=\"%s\" visited=\"%s\">\t%s</Line>" % (lineno+1, valid, visited, srclines[lineno]))
                else:
                    filereport.write("  <Line no=\"%d\" valid=\"%s\" visited=\"%s\"/>" % (lineno+1, valid, visited))

        totalLines += len(srclines)
        totalValid += validCount
        totalVisited += visitedCount

        if visitedCount > 0 and validCount > 0:
            score = (float(visitedCount) / float(validCount)) * 100
        else:
            score = 0

        if score == 100:
            reportFile.write("  <PerfectCoverage/> ")
        elif score == 0:
            reportFile.write("  <NoCoverage/> ")
        else:
            reportFile.write(filereport.getvalue())

        reportFile.write("  <FileSummary valid=\"%d\" visited=\"%d\" totalLines=\"%s\" coverage=\"%d\"/>" % (validCount, visitedCount, len(srclines), score))
        reportFile.write(" </File>")

endTime = time.clock()

reportFile.write("<Summary totalLines=\"%d\" totalVisited=\"%d\" totalValid=\"%d\" timeTaken=\"%.1f\"/>" % (totalLines, totalVisited, totalValid, endTime-startTime))

revisionCoverages = []
revisionCoverages.append(math.floor((float(totalVisited) / float(totalValid)) * 100))

if (len(history)) > 0:
    # Include delta histry
    lastRevisionSummaryNode = history[0].getElementsByTagName("CoverageReport")[0].getElementsByTagName("Summary")[0]
    lastRevisionLines = int(lastRevisionSummaryNode.getAttribute("totalLines"))
    lastRevisionVisted = int(lastRevisionSummaryNode.getAttribute("totalVisited"))
    lastRevisionValid = int(lastRevisionSummaryNode.getAttribute("totalValid"))

    reportFile.write("<DeltaFromLastRevision totalLines=\"%d\" totalVisited=\"%d\" totalValid=\"%d\"/>" % (
        totalLines-lastRevisionLines,
        totalVisited-lastRevisionVisted,
        totalValid-lastRevisionValid
    ))

    totalRevisions = len(history)
    currentRevision = 0

    for rev in history:
        summary = rev.getElementsByTagName("CoverageReport")[0].getElementsByTagName("Summary")[0]

        revisionTotalLines = int(summary.getAttribute("totalLines"))
        revisionTotalVisited = int(summary.getAttribute("totalVisited"))
        revisionTotalValid = int(summary.getAttribute("totalValid"))

        reportFile.write("<Revision id=\"%d\" totalLines=\"%d\" totalVisited=\"%d\" totalValid=\"%d\"/>" % (currentRevision,
            revisionTotalLines,
            revisionTotalVisited,
            revisionTotalValid
        ))

        currentRevision = currentRevision + 1
        revisionCoverages.append(math.floor((float(revisionTotalVisited) / float(revisionTotalValid)) * 100))

revisionCoverages.reverse()

while len(revisionCoverages) < 100:
    revisionCoverages.append(None)

if options.showGraph and len(history) > 2:
    chart = GChartWrapper.Line(revisionCoverages, scale=(0,100))
    chart.title('Coverage History', '0', 24)
    chart.axes.type('xy')
    chart.axes.label(*range(0, len(revisionCoverages)+1, 10))
    chart.axes.label(0, 25, 50, 75, 100)
    chart.color('0077CC')
    chart.size(800,200)
    chart.marker('s', '99EE99', 0, -1, 3)
    chart.line(1,0,0)

    reportFile.write("<SummaryGraph>%s</SummaryGraph>" % escape(str(chart)))

reportFile.write("</CoverageReport>")
reportFile.close()

if options.summary != None:
    summaryFile = open(options.summary, "wt")
    summaryFile.write("<CoverageReport>")
    summaryFile.write("<Summary totalLines=\"%d\" totalVisited=\"%d\" totalValid=\"%d\" timeTaken=\"%.1f\"/>" % (totalLines, totalVisited, totalValid, endTime-startTime))
    summaryFile.write("</CoverageReport>")
    summaryFile.close()

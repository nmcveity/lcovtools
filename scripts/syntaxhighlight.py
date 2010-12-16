"""
 Generates a HTML stream for Lua code to provide syntax highlighting
"""

from xml.sax.saxutils import escape
   
keywords = [
    "break",
    "do",
    "else",
    "elseif",
    "end", 
    "false",
    "for",
    "function",
    "if",
    "in",
    "local",
    "nil",
    "not",
    "or",
    "repeat",
    "return",
    "then",
    "true",
    "until",
    "while",
    "not",
    "and",
    "or",
]

whitespace = [
    "\t",
    "\n",
    " ",
]

operators = [
    "+",
    "-",
    "*",
    "/",
    "^",
    "%",
    "..",
    ".",
    "<",
    "<=",
    ">",
    ">=",
    "==",
    "~=",
    "-",
    "#",
    "=",
]

misc = [
    "...",
    ",",
    ":",
    ";",
    "[",
    "]",
    "{",
    "}",
    "(",
    ")",
]

standardLibrary = [
    "_G",
    "_VERSION",
    "assert",
    "collectgarbage",
    "dofile",
    "error",
    "getfenv",
    "getmetatable",
    "ipairs",
    "load",
    "loadfile",
    "loadstring",
    "module",
    "next",
    "pairs",
    "pcall",
    "print",
    "rawequal",
    "rawget",
    "rawset",
    "require",
    "select",
    "setfenv",
    "setmetatable",
    "tonumber",
    "tostring",
    "type",
    "unpack",
    "xpcall",
    
    "coroutine.create",
    "coroutine.resume",
    "coroutine.running",
    "coroutine.status",
    "coroutine.wrap",
    "coroutine.yield",

    "debug.debug",
    "debug.getfenv",
    "debug.gethook",
    "debug.getinfo",
    "debug.getlocal",
    "debug.getmetatable",
    "debug.getregistry",
    "debug.getupvalue",
    "debug.setfenv",
    "debug.sethook",
    "debug.setlocal",
    "debug.setmetatable",
    "debug.setupvalue",
    "debug.traceback",
    
    "io.close",
    "io.flush",
    "io.input",
    "io.lines",
    "io.open",
    "io.output",
    "io.popen",
    "io.read",
    "io.stderr",
    "io.stdin",
    "io.stdout",
    "io.tmpfile",
    "io.type",
    "io.write",
    
    "math.abs",
    "math.acos",
    "math.asin",
    "math.atan",
    "math.atan2",
    "math.ceil",
    "math.cos",
    "math.cosh",
    "math.deg",
    "math.exp",
    "math.floor",
    "math.fmod",
    "math.frexp",
    "math.huge",
    "math.ldexp",
    "math.log",
    "math.log10",
    "math.max",
    "math.min",
    "math.modf",
    "math.pi",
    "math.pow",
    "math.rad",
    "math.random",
    "math.randomseed",
    "math.sin",
    "math.sinh",
    "math.sqrt",
    "math.tan",
    "math.tanh",
    
    "os.clock",
    "os.date",
    "os.difftime",
    "os.execute",
    "os.exit",
    "os.getenv",
    "os.remove",
    "os.rename",
    "os.setlocale",
    "os.time",
    "os.tmpname",
    
    "package.cpath",
    "package.loaded",
    "package.loaders",
    "package.loadlib",
    "package.path",
    "package.preload",
    "package.seeall",
    
    "string.byte",
    "string.char",
    "string.dump",
    "string.find",
    "string.format",
    "string.gmatch",
    "string.gsub",
    "string.len",
    "string.lower",
    "string.match",
    "string.rep",
    "string.reverse",
    "string.sub",
    "string.upper",
    
    "table.concat",
    "table.insert",
    "table.maxn",
    "table.remove",
    "table.sort",
]

import re

tokenTypes = [
    ("blockcomment",            re.compile("\-\-\[\[.*\]\]", re.DOTALL)),
    ("comment",                 re.compile("\-\-.*")),
    ("string",                  re.compile("(@\s*\".*?\")|(\"([^\"\\\\]|\\\\.)*?\")")),             # double (") quoted strings
    ("string" ,                 re.compile("(@\s*'.*?')|('([^'\\\\]|\\\\.)*?')")),                  # single (') quoted strings
#    ("keyword",                 re.compile("\\W+|".join(["(" + re.escape(x) + ")" for x in keywords]))),
#    ("library",                 re.compile("\\W|".join([re.escape(x) for x in standardLibrary]))),
    ("whitespace",              re.compile("|".join([re.escape(x) for x in whitespace]))),
    ("misc" ,                   re.compile("|".join([re.escape(x) for x in misc]))),
    ("operator",                re.compile("|".join([re.escape(x) for x in operators]))),
    ("number",                  re.compile("[0-9]+")),
    ("identifier",              re.compile("[a-zA-Z_][a-zA-Z0-9_\\.]*")),
]

def whitespace_escape(str):
    """ Converts SPACE and TAB to NBSP """
    return str.replace(" ", "&nbsp;").replace("\t", "&nbsp;")
        
class LuaTokenizer:
    def __init__(self, sourceCode):
        self.src = sourceCode
        self.pos = 0
    
    def __iter__ (self):
        return self.next()
    
    def next(self):
        while self.pos < len(self.src):
            match = None
            matchType = None
            
            for tokenType in tokenTypes:
                match = tokenType[1].match(self.src, self.pos)
                matchType = tokenType[0]
                if match:
                    break
            
            if not match:
                raise "Failed to parse Lua source at %d:%s" % (self.pos, self.src[self.pos:self.pos+50])
            
            # Generators are cool
            yield matchType, match.group(0)
            
            # Consume everything matched by that regex
            self.pos = match.end(0)

class LuaHTMLLineOutput:
    def __init__(self, sourceCode):
        self.src = sourceCode
        self.pos = 0
        self.currentLine = ""
        
    def __iter__ (self):
        return self.next()
        
    def next(self):
        for matchType, matchValue in LuaTokenizer(self.src):
            if matchType == "whitespace" and matchValue == "\n":
                yield self.currentLine
                
                self.currentLine = ""
                self.pos += 1
            elif matchType == "whitespace" and matchValue == " ":
                self.currentLine += "&nbsp;"
                self.pos += 1
            elif matchType == "whitespace" and matchValue == "\t":
                self.currentLine += "&nbsp;&nbsp;&nbsp;&nbsp;"
                self.pos += 1
            elif matchType == "blockcomment":
                lines = matchValue.splitlines()
                if len(lines) > 1:
                    self.currentLine += "<span class=\"blockcomment\">"
                    for lineno, line in enumerate(lines):
                        self.currentLine += whitespace_escape(escape(line)) + "</span>"
                        if lineno < (len(lines)-1):
                            yield self.currentLine
                            self.currentLine = "<span class=\"blockcomment\">"
                else:
                    self.currentLine += "<span class=\"blockcomment\">%s</span>" % escape(matchValue)
            elif matchType == "identifier":
                if matchValue in keywords:
                    self.currentLine += "<span class=\"keyword\">%s</span>" % escape(matchValue)
                elif matchValue in standardLibrary:
                    self.currentLine += "<span class=\"library\">%s</span>" % escape(matchValue)
                else:
                    self.currentLine += "<span class=\"identifier\">%s</span>" % escape(matchValue)
            else:
                self.currentLine += "<span class=\"%s\">%s</span>" % (matchType, escape(matchValue))

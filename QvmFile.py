#!/usr/bin/env python

# Copyright (C) 2012, 2020 Angelo Cano
#
# This file is part of Qvmdis.
#
# Qvmdis is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Qvmdis is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Qvmdis.  If not, see <https://www.gnu.org/licenses/>.

import os.path, struct, sys
from LEBinFile import LEBinFile

# python hash() builtin gives different values for 32-bit and 64-bit implementations
# http://effbot.org/zone/python-hash.htm

def c_mul(a, b):
    #v = eval(hex((long(a) * b) & 0xFFFFFFFFL)[:-1])
    # 32-bit signed
    v = a * b
    v = v & 0xffffffff

    if v > 0x7fffffff:
        v = -(0x100000000 - v)
    return v

def hash32BitSigned (str):
    if not str:
        return 0  # empty
    value = ord(str[0]) << 7
    for char in str:
        value = c_mul(1000003, value) ^ ord(char)
    value = value ^ len(str)
    if value == -1:
        value = -2
    return value

def atoi (s, base=10):
    return int(s, base)

# python 3 byte string ord() and chr() compatibility
#
#  s = b'\x00\x01\x02\x03'
#    python 2:  b[0] is '\x00'
#    python 3:  b[0] is 0
#
# slices are ok:  s[0:2] is b'\x00\x01' in both versions
#
# probably would have been easier to always access as slice to get a byte
# string instead of xord() and xchr().  Ex:  s[0:1] instead of s[0]

def xord (s):
    if isinstance(s, int):
        return s
    else:
        return ord(s)

def xchr (i):
    if isinstance(i, str):
        return i
    else:
        return chr(i)

# q3vm_specs.html wrong about header

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

CGAME_SYSCALLS_ASM_FILE = os.path.join(BASE_DIR, "cg_syscalls.asm")
GAME_SYSCALLS_ASM_FILE = os.path.join(BASE_DIR, "g_syscalls.asm")
UI_SYSCALLS_ASM_FILE = os.path.join(BASE_DIR, "ui_syscalls.asm")

BASEQ3_CGAME_FUNCTIONS_FILE = os.path.join(BASE_DIR, "baseq3-cgame-functions.hmap")
BASEQ3_GAME_FUNCTIONS_FILE = os.path.join(BASE_DIR, "baseq3-game-functions.hmap")
BASEQ3_UI_FUNCTIONS_FILE = os.path.join(BASE_DIR, "baseq3-ui-functions.hmap")

SYMBOLS_FILE = "symbols.dat"
FUNCTIONS_FILE = "functions.dat"
CONSTANTS_FILE = "constants.dat"
COMMENTS_FILE = "comments.dat"

def output (msg):
    sys.stdout.write(msg)

def error_msg (msg):
    # send to both stdout and stderr since output is usually redirected to file
    sys.stdout.write("---- error occurred : %s\n" % msg)
    sys.stderr.write("ERROR: %s\n" % msg)

def error_exit (msg, exitValue = 1):
    error_msg(msg)
    sys.exit(exitValue)

class Opcode:
    def __init__ (self, val, name, parmSize):
        self.val = val
        self.name = name
        self.parmSize = parmSize

OP_NAME = 0
OP_PARM_SIZE = 1
OP_JUMP_PARM = 2
OP_STACK_CHANGE = 3

opcodes = [ \
    ["undef", 0, False, 0],
    ["ignore", 0, False, 0],
    ["break", 0, False, 0],
    ["enter", 4, False, 0],  #FIXME OP_STACK_CHANGE
    ["leave", 4, False, 0],
    ["call", 0, False, -1],  #FIXME OP_STACK_CHANGE
    ["push", 0, False, 1],
    ["pop", 0, False, -1],
    ["const", 4, False, 1],
    ["local", 4, False, 1],
    ["jump", 0, False, -1],
    ["eq", 4, True, -2],
    ["ne", 4, True, -2],
    ["lti", 4, True, -2],
    ["lei", 4, True, -2],
    ["gti", 4, True, -2],
    ["gei", 4, True, -2],
    ["ltu", 4, True, -2],
    ["leu", 4, True, -2],
    ["gtu", 4, True, -2],
    ["geu", 4, True, -2],
    ["eqf", 4, True, -2],
    ["nef", 4, True, -2],
    ["ltf", 4, True, -2],
    ["lef", 4, True, -2],
    ["gtf", 4, True, -2],
    ["gef", 4, True, -2],
    ["load1", 0, False, 0],
    ["load2", 0, False, 0],
    ["load4", 0, False, 0],
    ["store1", 0, False, -2],
    ["store2", 0, False, -2],
    ["store4", 0, False, -2],
    ["arg", 1, False, -1],
    ["block_copy", 4, False, -2],  # docs wrong?
    ["sex8", 0, False, 0],
    ["sex16", 0, False, 0],
    ["negi", 0, False, 0],
    ["add", 0, False, -1],
    ["sub", 0, False, -1],
    ["divi", 0, False, -1],
    ["divu", 0, False, -1],
    ["modi", 0, False, -1],
    ["modu", 0, False, -1],
    ["muli", 0, False, -1],
    ["mulu", 0, False, -1],
    ["band", 0, False, -1],
    ["bor", 0, False, -1],
    ["bxor", 0, False, -1],
    ["bcom", 0, False, 0],
    ["lsh", 0, False, -1],
    ["rshi", 0, False, -1],
    ["rshu", 0, False, -1],
    ["negf", 0, False, 0],
    ["addf", 0, False, -1],
    ["subf", 0, False, -1],
    ["divf", 0, False, -1],
    ["mulf", 0, False, -1],
    ["cvif", 0, False, 0],
    ["cvfi", 0, False, 0]
]

class InvalidQvmFile(Exception):
    pass

class QvmFile(LEBinFile):
    magic = 0x12721444

    # qvmType:("cgame", "game", "ui", None)
    def __init__ (self, qvmFileName, qvmType=None):
        self._file = open(qvmFileName, "rb")
        m = self.read_int()
        if m != self.magic:
            raise InvalidQvmFile("not a valid qvm file  0x%x != 0x%x" % (m, self.magic))

        self.instructionCount = self.read_int()
        self.codeSegOffset = self.read_int()
        self.codeSegLength = self.read_int()
        self.dataSegOffset = self.read_int()
        self.dataSegLength = self.read_int()
        self.litSegOffset = self.dataSegOffset + self.dataSegLength
        self.litSegLength = self.read_int()
        self.bssSegOffset = self.dataSegOffset + self.dataSegLength + self.litSegLength
        self.bssSegLength = self.read_int()

        self.seek (self.codeSegOffset)
        self.codeData = self.read(self.codeSegLength)
        self.codeData = self.codeData + b"\x00\x00\x00\x00\x00"  # for look ahead
        self.seek (self.dataSegOffset)
        self.dataData = self.read(self.dataSegLength)
        self.dataData = self.dataData + b"\x00\x00\x00\x00"  # for look ahead

        self.seek (self.litSegOffset)
        self.litData = self.read(self.litSegLength)
        self.litData = self.litData + b"\x00\x00\x00\x00"  # for look ahead

        self.syscalls = {}  # num:int -> name:str
        self.functions = {}  # addr:int -> name:str

        # user labels
        self.functionsArgLabels = {}  # addr:int -> { argX:str -> sym:str }
        self.functionsLocalLabels = {}  # addr:int -> { localAddr:int -> sym:str }
        self.functionsLocalRangeLabels = {}  # addr:int -> { localAddr:int -> [ [size1:int, sym1:str], [size2:int, sym2:str], ... ] }

        self.functionHashes = {}  # addr:int -> hash:int
        self.functionRevHashes = {}  # hash:int -> [funcAddr1:int, funcAddr2:int, ...]
        self.functionSizes = {}  # addr:int -> instructionCount:int
        self.functionMaxArgsCalled = {}  # addr:int -> maxArgs:int
        self.functionParmNum = {}  # addr:int -> num:int

        self.baseQ3FunctionRevHashes = {}  # hash:int -> [ funcName1, funcName2, ... ]

        self.symbols = {}  # addr:int -> sym:str
        self.symbolsRange = {}  # addr:int -> [ [size1:int, sym1:str], [size2:int, sym2:str], ... ]
        self.constants = {}  # codeAddr:int -> [ name:str, value:int ]

        # code segment comments
        self.commentsInline = {}  # addr:int -> comment:str
        self.commentsBefore = {}  # addr:int -> [ line1:str, line2:str, ... ]
        self.commentsBeforeSpacing = {}  # addr:int -> [ spaceBefore:int, spaceAfter:int ]
        self.commentsAfter = {}  # addr:int -> [ line1:str, line2:str, ... ]
        self.commentsAfterSpacing = {}  # addr:int -> [ spaceBefore:int, spaceAfter: int ]

        # data segment comments
        self.dataCommentsInline = {}  # addr:int -> comment:str
        self.dataCommentsBefore = {}  # addr:int -> [ line1:str, line2:str, ... ]
        self.dataCommentsBeforeSpacing = {}  # addr:int -> [ spaceBefore:int, spaceAfter:int ]
        self.dataCommentsAfter = {}  # addr:int -> [ line1:str, line2:str, ... ]
        self.dataCommentsAfterSpacing = {}  # addr:int -> [ spaceBefore:int, spaceAfter: int ]

        self.jumpPoints = {}  # targetAddr:int -> [ jumpPointAddr1:int, jumpPointAddr2:int, ... ]
        self.callPoints = {}  # targetAddr:int -> [ callerAddr1:int, callerAddr2:int, ... ]

        self.set_qvm_type(qvmType)
        self.load_address_info()
        self.compute_function_info()

    def set_qvm_type (self, qvmType):
        self.qvmType = qvmType

        if qvmType not in ("cgame", "game", "ui"):
            return

        if qvmType == "cgame":
            fname = CGAME_SYSCALLS_ASM_FILE
            f = open(fname)
        elif qvmType == "game":
            fname = GAME_SYSCALLS_ASM_FILE
            f = open(fname)
        elif qvmType == "ui":
            fname = UI_SYSCALLS_ASM_FILE
            f = open(fname)

        lines = f.readlines()
        f.close()

        lineCount = 0
        for line in lines:
            words = line.split()
            if len(words) == 3:
                try:
                    self.syscalls[atoi(words[2])] = words[1]
                except ValueError:
                    error_exit("couldn't parse system call number in line %d of %s: %s" % (lineCount + 1, fname, line))
            lineCount += 1

        if qvmType == "cgame":
            fname = BASEQ3_CGAME_FUNCTIONS_FILE
            f = open(fname)
        elif qvmType == "game":
            fname = BASEQ3_GAME_FUNCTIONS_FILE
            f = open(fname)
        elif qvmType == "ui":
            fname = BASEQ3_UI_FUNCTIONS_FILE
            f = open(fname)

        lines = f.readlines()
        f.close()
        lineCount = 0
        for line in lines:
            words = line.split()
            if len(words) > 2:
                n = words[1]
                try:
                    h = atoi(words[2], 16)
                except ValueError:
                    error_exit("couldn't parse hash value in line %d of %s: %s" % (lineCount + 1, fname, line))
                if h in self.baseQ3FunctionRevHashes:
                    self.baseQ3FunctionRevHashes[h].append(n)
                else:
                    self.baseQ3FunctionRevHashes[h] = [n]
            lineCount += 1

    def load_address_info (self):
        fname = SYMBOLS_FILE
        if os.path.exists(fname):
            f = open(fname)
            lines = f.readlines()
            f.close()
            lineCount = 0
            for line in lines:
                # strip comments
                line = line.split(";")[0]
                words = line.split()
                if len(words) == 2:
                    try:
                        self.symbols[atoi(words[0], 16)] = words[1]
                    except ValueError:
                        error_exit("couldn't parse address in line %d of %s: %s" % (lineCount + 1, fname, line))
                elif len(words) == 3:
                    try:
                        addr = atoi(words[0], 16)
                        size = atoi(words[1], 16)
                    except ValueError:
                        error_exit("couldn't parse address or size in line %d of %s: %s" % (lineCount + 1, fname, line))
                    sym = words[2]
                    if not addr in self.symbolsRange:
                        self.symbolsRange[addr] = []
                    self.symbolsRange[addr].append([size, sym])

                lineCount += 1

        fname = FUNCTIONS_FILE
        if os.path.exists(fname):
            f = open(fname)
            lines = f.readlines()
            f.close()
            lineCount = 0
            currentFuncAddr = None
            while lineCount < len(lines):
                line = lines[lineCount]
                # strip comments
                line = line.split(";")[0]
                words = line.split()
                if len(words) > 1:
                    if words[0].startswith("arg"):
                        if currentFuncAddr == None:
                            error_exit("function not defined yet in line %d of %s: %s" % (lineCount + 1, fname, line))
                        if not currentFuncAddr in self.functionsArgLabels:
                            self.functionsArgLabels[currentFuncAddr] = {}
                        self.functionsArgLabels[currentFuncAddr][words[0]] = words[1]
                    elif words[0] == "local":
                        if currentFuncAddr == None:
                            error_exit("function not defined yet in line %d of %s: %s" % (lineCount + 1, fname, line))
                        if len(words) < 3:
                            error_exit("invalid local specification in line %d of %s: %s" % (lineCount + 1, fname, line))
                        if len(words) > 3:  # range specified
                            try:
                                localAddr = atoi(words[1], 16)
                                size = atoi(words[2], 16)
                            except ValueError:
                                error_exit("couldn't parse address or size of range in line %d of %s: %s" % (lineCount + 1, fname, line))

                            sym = words[3]
                            if not currentFuncAddr in self.functionsLocalRangeLabels:
                                self.functionsLocalRangeLabels[currentFuncAddr] = {}
                            if not localAddr in self.functionsLocalRangeLabels[currentFuncAddr]:
                                self.functionsLocalRangeLabels[currentFuncAddr][localAddr] = []
                            self.functionsLocalRangeLabels[currentFuncAddr][localAddr].append([size, sym])
                        else:
                            if not currentFuncAddr in self.functionsLocalLabels:
                                self.functionsLocalLabels[currentFuncAddr] = {}
                            try:
                                self.functionsLocalLabels[currentFuncAddr][atoi(words[1], 16)] = words[2]
                            except ValueError:
                                error_exit("couldn't parse address in line %d of %s: %s" % (lineCount + 1, fname, line))
                    else:
                        # function definition
                        try:
                            funcAddr = atoi(words[0], 16)
                        except ValueError:
                            error_exit("couldn't parse address in line %d of %s: %s" % (lineCount + 1, fname, line))
                        self.functions[funcAddr] = words[1]
                        currentFuncAddr = funcAddr

                lineCount += 1

        fname = CONSTANTS_FILE
        if os.path.exists(fname):
            f = open(fname)
            lines = f.readlines()
            f.close()
            lineCount = 0
            for line in lines:
                # strip comments
                line = line.split(";")[0]
                words = line.split()
                if len(words) > 2:
                    try:
                        codeAddr = atoi(words[0], 16)
                        n = words[1]
                        val = atoi(words[2], 16)
                    except ValueError:
                        error_exit("couldn't parse address or value in line %d of %s: %s" % (lineCount + 1, fname, line))
                    self.constants[codeAddr] = [n, val]

                lineCount += 1

        fname = COMMENTS_FILE
        if os.path.exists(fname):
            f = open(fname)
            lines = f.readlines()
            f.close()
            lineCount = 0
            while lineCount < len(lines):
                line = lines[lineCount]
                # strip comments
                line = line.split(";")[0]

                words = line.split()
                dataComment = False
                if len(words) > 1:
                    if words[0] == "d":
                        dataComment = True
                        del words[0]

                if len(words) > 1:
                    try:
                        codeAddr = atoi(words[0], 16)
                    except ValueError:
                        error_exit("couldn't get address in line %d of %s: %s" % (lineCount + 1, fname, line))
                    commentType = words[1]

                    if commentType == "inline":
                        if len(words) > 2:
                            comment = line[line.find(words[2]):].rstrip()
                            if dataComment:
                                self.dataCommentsInline[codeAddr] = comment
                            else:
                                self.commentsInline[codeAddr] = comment
                    elif commentType == "before"  or  commentType == "after":
                        spaceBefore = 0
                        spaceAfter = 0
                        if len(words) > 2:
                            try:
                                spaceBefore = atoi(words[2])
                                if len(words) > 3:
                                    spaceAfter = atoi(words[3])
                            except ValueError:
                                error_exit("couldn't get space before or after value in line %d of %s: %s" % (lineCount + 1, fname, line))

                        if spaceBefore > 0  or spaceAfter > 0:
                            if commentType == "before":
                                if dataComment:
                                    self.dataCommentsBeforeSpacing[codeAddr] = [spaceBefore, spaceAfter]
                                else:
                                    self.commentsBeforeSpacing[codeAddr] = [spaceBefore, spaceAfter]
                            else:
                                if dataComment:
                                    self.dataCommentsAfterSpacing[codeAddr] = [spaceBefore, spaceAfter]
                                else:
                                    self.commentsAfterSpacing[codeAddr] = [spaceBefore, spaceAfter]
                        if commentType == "before":
                            if dataComment:
                                self.dataCommentsBefore[codeAddr] = []
                            else:
                                self.commentsBefore[codeAddr] = []
                        else:
                            if dataComment:
                                self.dataCommentsAfter[codeAddr] = []
                            else:
                                self.commentsAfter[codeAddr] = []

                        lineCount += 1
                        while lineCount < len(lines):
                            line = lines[lineCount]
                            if line[:-1] == "<<<":
                                break
                            else:
                                if commentType == "before":
                                    if dataComment:
                                        self.dataCommentsBefore[codeAddr].append(line[:-1])
                                    else:
                                        self.commentsBefore[codeAddr].append(line[:-1])
                                else:
                                    if dataComment:
                                        self.dataCommentsAfter[codeAddr].append(line[:-1])
                                    else:
                                        self.commentsAfter[codeAddr].append(line[:-1])
                            lineCount += 1
                    else:
                        error_exit("invalid comment type in line %d of %s: %s" % (lineCount + 1, fname, line))

                lineCount += 1

    def print_header (self):
        output("; instruction count: 0x%x\n" % self.instructionCount)
        output("; CODE seg offset: 0x%08x  length: 0x%x\n" % (self.codeSegOffset, self.codeSegLength))
        output("; DATA seg offset: 0x%08x  length: 0x%x\n" % (self.dataSegOffset, self.dataSegLength))
        output("; LIT  seg offset: 0x%08x  length: 0x%x\n" % (self.litSegOffset, self.litSegLength))
        output("; BSS  seg offset: 0x%08x  length: 0x%x\n" % (self.bssSegOffset, self.bssSegLength))

    def print_code_disassembly (self):
        pos = 0

        count = -1
        currentFuncAddr = None
        while count < self.instructionCount - 1:
            count += 1

            comment = None
            opcStr = self.codeData[pos]
            opc = xord(opcStr)
            pos += 1
            name = opcodes[opc][OP_NAME]
            psize = opcodes[opc][OP_PARM_SIZE]

            if name != "enter"  and  count in self.commentsBefore:
                if count in self.commentsBeforeSpacing:
                    for i in range(self.commentsBeforeSpacing[count][0]):
                        output("\n")
                for line in self.commentsBefore[count]:
                    output("; %s\n" % line)
                if count in self.commentsBeforeSpacing:
                    for i in range(self.commentsBeforeSpacing[count][1]):
                        output("\n")

            if psize == 0:
                parm = None
            elif psize == 1:
                parmStr = self.codeData[pos]
                parm = xord(parmStr)
                pos += 1
            elif psize == 4:
                parmStr = self.codeData[pos : pos + psize]
                parm = struct.unpack("<l", parmStr)[0]
                pos += 4
            else:
                error_exit("FIXME bad opcode size")

            if count in self.jumpPoints:
                output("\n;----------------------------------- from ")
                for jp in self.jumpPoints[count]:
                    output(" 0x%x" % jp)
                output("\n")

            if name == "enter":
                addr = count
                currentFuncAddr = addr
                stackAdjust = parm
                if count in self.callPoints:
                    output("\n; called from")
                    for caller in self.callPoints[count]:
                        if caller in self.functions:
                            output(" %s()" % self.functions[caller])
                        elif self.functionHashes[caller] in self.baseQ3FunctionRevHashes:
                            for n in self.baseQ3FunctionRevHashes[self.functionHashes[caller]]:
                                output(" ?%s()" % n)
                        else:
                            output(" 0x%x" % caller)
                    output("\n")

                output("\n")

                if addr in self.functions:
                    output("; func %s()\n" % self.functions[count])
                elif self.functionHashes[addr] in self.baseQ3FunctionRevHashes:
                    output(";")
                    for n in self.baseQ3FunctionRevHashes[self.functionHashes[addr]]:
                        output(" ?%s()" % n)
                    output("\n")
                if addr in self.functionParmNum:
                    output(";")
                    p = self.functionParmNum[addr]
                    if p == 0:
                        output(" no")
                    elif p == -1:
                        output(" var")
                    else:
                        output(" 0x%x" % p)
                    output(" args\n")

                output("; max local arg 0x%x\n" % self.functionMaxArgsCalled[addr])
                output("; ========================\n")

                if count in self.commentsBefore:
                    if count in self.commentsBeforeSpacing:
                        for i in range(self.commentsBeforeSpacing[count][0]):
                            output("\n")
                    for line in self.commentsBefore[count]:
                        output("; %s\n" % line)
                    if count in self.commentsBeforeSpacing:
                        for i in range(self.commentsBeforeSpacing[count][1]):
                            output("\n")

            elif name == "local":
                argNum = parm - stackAdjust - 0x8
                if argNum >= 0:
                    argstr = "arg%d" % (argNum / 4)
                    comment = argstr
                    if currentFuncAddr in self.functionsArgLabels:
                        if argstr in self.functionsArgLabels[currentFuncAddr]:
                            comment = comment + " : " + self.functionsArgLabels[currentFuncAddr][argstr]
                else:
                    if currentFuncAddr in self.functionsLocalLabels:
                        if parm in self.functionsLocalLabels[currentFuncAddr]:
                            comment = self.functionsLocalLabels[currentFuncAddr][parm]
                    elif currentFuncAddr in self.functionsLocalRangeLabels:
                        # find the closest match
                        exactMatches = []  #FIXME sorted
                        match = None
                        matchDiff = 0
                        matchSym = ""
                        matchRangeSize = 0
                        for localAddr in self.functionsLocalRangeLabels[currentFuncAddr]:
                            for r in self.functionsLocalRangeLabels[currentFuncAddr][localAddr]:
                                size = r[0]
                                sym = r[1]
                                if parm == localAddr:
                                    exactMatches.append(sym)
                                elif parm >= localAddr  and  parm < (localAddr + size):
                                    if match == None:
                                        match = localAddr
                                        matchDiff = parm - localAddr
                                        matchSym = sym
                                        matchRangeSize = size
                                    elif (parm - localAddr) < matchDiff:
                                        match = localAddr
                                        matchDiff = parm - localAddr
                                        matchSym = sym
                                        matchRangeSize = size
                                    elif (parm - localAddr) == matchDiff:  # multiple ranges beginning at same address
                                        # pick smallest
                                        if size < matchRangeSize:
                                            match = localAddr
                                            matchDiff = parm - localAddr
                                            matchSym = sym
                                            matchRangeSize = size
                        if len(exactMatches) > 0:
                            comment =  ", ".join(exactMatches)
                        else:
                            if match != None:
                                comment = "%s + 0x%x" % (matchSym, matchDiff)
            elif name == "const":
                nextOp = xord(self.codeData[pos])

                if count in self.constants:
                    if parm != self.constants[count][1]:
                        comment = "FIXME constant val != to code val"
                    else:
                        comment = self.constants[count][0]

                elif parm >= self.dataSegLength  and  parm < self.dataSegLength + self.litSegLength  and  opcodes[nextOp][OP_NAME] not in ("call", "jump"):
                    chars = []
                    i = 0
                    while 1:
                        c = xord(self.litData[parm - self.dataSegLength + i])
                        if c == xord(b'\0'):
                            break
                        elif c == xord(b'\n'):
                            chars.extend(('\\', 'n'))
                        elif c == xord(b'\t'):
                            chars.extend(('\\', 't'))
                        elif c > 31  and  c < 127:
                            chars.append(xchr(c))
                        else:
                            chars.extend(('\\', 'x', "%x" % c))
                        i += 1
                    output("\n  ; \"%s\"\n" % "".join(chars))
                elif parm >= 0  and  parm < self.dataSegLength  and  opcodes[nextOp][OP_NAME] not in ("call", "jump"):
                    b0 = xchr(self.dataData[parm])
                    b1 = xchr(self.dataData[parm + 1])
                    b2 = xchr(self.dataData[parm + 2])
                    b3 = xchr(self.dataData[parm + 3])

                    output("\n  ; %02x %02x %02x %02x  (0x%x)\n" % (xord(b0), xord(b1), xord(b2), xord(b3), struct.unpack("<L", self.dataData[parm:parm+4])[0]))

                    if parm in self.symbols:
                        comment = self.symbols[parm]
                    else:  # check symbol ranges
                        exactMatches = []  #FIXME sorted
                        match = None
                        matchDiff = 0
                        matchSym = ""
                        matchRangeSize = 0
                        for rangeAddr in self.symbolsRange:
                            for r in self.symbolsRange[rangeAddr]:
                                size = r[0]
                                sym = r[1]
                                if parm == rangeAddr:
                                    exactMatches.append(sym)
                                elif parm >= rangeAddr  and  parm < (rangeAddr + size):
                                    if match == None:
                                        match = rangeAddr
                                        matchSym = sym
                                        matchDiff = parm - rangeAddr
                                        matchRangeSize = size
                                    elif (parm - rangeAddr) < matchDiff:
                                        match = rangeAddr
                                        matchSym = sym
                                        matchDiff = parm - rangeAddr
                                        matchRangeSize = size
                                    elif (parm - rangeAddr) == matchDiff:  # multiple ranges beginning at same address
                                        # pick smallest
                                        if size < matchRangeSize:
                                            match = rangeAddr
                                            matchSym = sym
                                            matchDiff = parm - rangeAddr
                                            matchRangeSize = size
                        if len(exactMatches) > 0:
                            comment =  ", ".join(exactMatches)
                        else:
                            if match != None:
                                comment = "%s + 0x%x" % (matchSym, matchDiff)

                elif opcodes[nextOp][OP_NAME] == "call":
                    if parm < 0  and  parm in self.syscalls:
                        comment = "%s()" % self.syscalls[parm]
                    elif parm in self.functions:
                        comment = "%s()" % self.functions[parm]
                    elif parm in self.functionHashes:
                        if self.functionHashes[parm] in self.baseQ3FunctionRevHashes:
                            comment = ""
                            for n in self.baseQ3FunctionRevHashes[self.functionHashes[parm]]:
                                comment += " ?%s()" % n
                        else:
                            comment = ":unknown function:"

                elif parm >= self.dataSegLength  and  opcodes[nextOp][OP_NAME] not in ("call", "jump"):
                    # bss segment
                    #FIXME check that it doesn't go past??
                    if parm in self.symbols:
                        comment = self.symbols[parm]
                    else:  # check symbol ranges
                        exactMatches = []  #FIXME sorted
                        match = None
                        matchDiff = 0
                        matchSym = ""
                        matchRangeSize = 0
                        for rangeAddr in self.symbolsRange:
                            for r in self.symbolsRange[rangeAddr]:
                                size = r[0]
                                sym = r[1]
                                if parm == rangeAddr:
                                    exactMatches.append(sym)
                                elif parm >= rangeAddr  and  parm < (rangeAddr + size):
                                    if match == None:
                                        match = rangeAddr
                                        matchSym = sym
                                        matchDiff = parm - rangeAddr
                                        matchRangeSize = size
                                    elif (parm - rangeAddr) < matchDiff:
                                        match = rangeAddr
                                        matchSym = sym
                                        matchDiff = parm - rangeAddr
                                        matchRangeSize = size
                                    elif (parm - rangeAddr) == matchDiff:  # multiple ranges beginning at same address
                                        # pick smallest
                                        if size < matchRangeSize:
                                            match = rangeAddr
                                            matchSym = sym
                                            matchDiff = parm - rangeAddr
                                            matchRangeSize = size
                        if len(exactMatches) > 0:
                            comment =  ", ".join(exactMatches)
                        else:
                            if match != None:
                                comment = "%s + 0x%x" % (matchSym, matchDiff)

            sc = opcodes[opc][OP_STACK_CHANGE]
            if sc != 0  or parm != None:
                output("%08x  %-13s" % (count, name))
            else:
                output("%08x  %s" % (count, name))

            if sc < 0:
                output("  %d" % sc)
            elif sc > 0:
                output("   %d" % sc)
            else:
                if parm != None  or  comment  or count in self.commentsInline:
                    output("    ")

            if parm != None:
                if parm < 0:
                    output("  -0x%x" % -parm)
                else:
                    output("   0x%x" % parm)

            if comment:
                output("  ; %s" % comment)

            if count in self.commentsInline:
                output("  ; %s" % self.commentsInline[count])

            # finish printing line
            output("\n")

            if count in self.commentsAfter:
                if count in self.commentsAfterSpacing:
                    for i in range(self.commentsAfterSpacing[count][0]):
                        output("\n")
                for line in self.commentsAfter[count]:
                    output("; %s\n" % line)
                if count in self.commentsAfterSpacing:
                    for i in range(self.commentsAfterSpacing[count][1]):
                        output("\n")

    def print_data_disassembly (self):
        count = 0
        while count < self.dataSegLength:
            if count in self.dataCommentsBefore:
                if count in self.dataCommentsBeforeSpacing:
                    for i in range(self.dataCommentsBeforeSpacing[count][0]):
                        output("\n")
                for line in self.dataCommentsBefore[count]:
                    output("; %s\n" % line)
                if count in self.dataCommentsBeforeSpacing:
                    for i in range(self.dataCommentsBeforeSpacing[count][1]):
                        output("\n")

            output("0x%08x  " % count)
            b0 = self.dataData[count]
            b1 = self.dataData[count + 1]
            b2 = self.dataData[count + 2]
            b3 = self.dataData[count + 3]

            output(" %02x %02x %02x %02x    0x%x" % (xord(b0), xord(b1), xord(b2), xord(b3), struct.unpack("<L", self.dataData[count:count+4])[0]))
            if count in self.dataCommentsInline:
                output("  ; %s" % self.dataCommentsInline[count])

            # finish printing line
            output("\n")

            if count in self.dataCommentsAfter:
                if count in self.dataCommentsAfterSpacing:
                    for i in range(self.dataCommentsAfterSpacing[count][0]):
                        output("\n")
                for line in self.dataCommentsAfter[count]:
                    output("; %s\n" % line)
                if count in self.dataCommentsAfterSpacing:
                    for i in range(self.dataCommentsAfterSpacing[count][1]):
                        output("\n")

            count += 4

    def print_lit_disassembly (self):
        pos = self.dataSegLength
        offset = 0
        while offset < self.litSegLength:
            count = offset + pos
            if count in self.dataCommentsBefore:
                if count in self.dataCommentsBeforeSpacing:
                    for i in range(self.dataCommentsBeforeSpacing[count][0]):
                        output("\n")
                for line in self.dataCommentsBefore[count]:
                    output("; %s\n" % line)
                if count in self.dataCommentsBeforeSpacing:
                    for i in range(self.dataCommentsBeforeSpacing[count][1]):
                        output("\n")

            output("0x%08x  " % (offset + pos))
            chars = []
            i = 0
            while 1:
                c = xord(self.litData[offset + i])
                if c == xord(b'\n'):
                    chars.extend(('\\', 'n'))
                elif c == xord(b'\t'):
                    chars.extend(('\\', 't'))
                elif xord(c) > 31  and  xord(c) < 127:
                    chars.append(xchr(c))
                elif c == xord(b'\0')  or  offset + i >= self.litSegLength:
                    output("\"%s\"" %  "".join(chars))

                    if count in self.dataCommentsInline:
                        output("  ; %s" % self.dataCommentsInline[count])

                    # finish printing line
                    output("\n")

                    if count in self.dataCommentsAfter:
                        if count in self.dataCommentsAfterSpacing:
                            for j in range(self.dataCommentsAfterSpacing[count][0]):
                                output("\n")
                        for line in self.dataCommentsAfter[count]:
                            output("; %s\n" % line)
                        if count in self.dataCommentsAfterSpacing:
                            for j in range(self.dataCommentsAfterSpacing[count][1]):
                                output("\n")

                    offset = offset + i
                    break
                else:
                    # not printable (< 31 or > 127) and not tab or newline
                    if len(chars) > 0:
                        output("\"%s\" " % "".join(chars))
                        chars = []
                    output(" 0x%x  " % xord(c))

                i += 1

            offset += 1

    def compute_function_info (self):
        pos = 0
        funcStartInsNum = -1
        funcInsCount = 0
        funcOffset = 0
        funcHashSum = ""
        maxArgs = 0x8
        lastArg = 0x0

        opcStr = "\x00"
        opc = 0
        parmStr = "\x00"
        parm = 0

        prevOpcStr = "\x00"
        prevOpc = 0
        prevOpcParmStr = "\x00"
        prevOpcParm = 0

        ins = -1
        while ins < self.instructionCount - 1:
            ins += 1

            prevOpcStr = opcStr
            prevOpc = opc
            prevParmStr = parmStr
            prevParm = parm

            opcStr = xchr(self.codeData[pos])
            opc = xord(opcStr)
            funcInsCount += 1
            funcHashSum += "%d" % opc
            pos += 1
            name = opcodes[opc][OP_NAME]
            psize = opcodes[opc][OP_PARM_SIZE]
            if psize:
                parmStr = self.codeData[pos : pos + psize]
                if psize == 1:
                    parm = xord(parmStr)
                elif psize == 4:
                    parm = struct.unpack("<l", parmStr)[0]
                else:
                    parm = None
            else:
                parmStr = None
                parm = None
            pos += psize

            if name == "const":
                if parm < 0:
                    funcHashSum += "%d" % parm
            elif name == "pop":
                lastArg = 0
            elif name == "local":
                funcHashSum += "%d" % parm
            elif name == "arg":
                if parm > maxArgs:
                    maxArgs = parm
                lastArg = parm
            elif name == "enter":
                if pos > 5:   # else it's first function of file  vmMain()
                    self.functionSizes[funcStartInsNum] = funcInsCount
                    h = hash32BitSigned(funcHashSum)
                    self.functionHashes[funcStartInsNum] = h
                    if h in self.functionRevHashes:
                        self.functionRevHashes[h].append (funcStartInsNum)
                    else:
                        self.functionRevHashes[h] = [funcStartInsNum]
                    self.functionMaxArgsCalled[funcStartInsNum] = maxArgs
                funcStartInsNum = ins
                funcOffset = pos - psize - 1
                funcInsCount = 1
                funcHashSum = ""
                maxArgs = 0x8
                lastArg = 0
            elif opcodes[opc][OP_NAME] == "jump":
                if opcodes[prevOpc][OP_NAME] == "const":
                    if prevParm in self.jumpPoints:
                        self.jumpPoints[prevParm].append (ins)
                    else:
                        self.jumpPoints[prevParm] = [ins]
            elif opcodes[opc][OP_JUMP_PARM]:
                if parm in self.jumpPoints:
                    self.jumpPoints[parm].append (ins)
                else:
                    self.jumpPoints[parm] = [ins]
            elif name == "call":
                if opcodes[prevOpc][OP_NAME] == "const":
                    if prevParm in self.callPoints:
                        self.callPoints[prevParm].append (funcStartInsNum)
                    else:
                        self.callPoints[prevParm] = [funcStartInsNum]
                    if prevParm in self.functionParmNum:
                        x = self.functionParmNum[prevParm]
                        if x != -1:
                            if x != lastArg:
                                self.functionParmNum[prevParm] = -1
                    else:
                        self.functionParmNum[prevParm] = lastArg
        self.functionSizes[funcStartInsNum] = funcInsCount
        h = hash32BitSigned(funcHashSum)
        self.functionHashes[funcStartInsNum] = h
        if h in self.functionRevHashes:
            self.functionRevHashes[h].append (funcStartInsNum)
        else:
            self.functionRevHashes[h] = [funcStartInsNum]
        self.functionMaxArgsCalled[funcStartInsNum] = maxArgs

    def print_function_hashes (self):
        ks = sorted(self.functionHashes.keys())

        for addr in ks:
            output("0x%08x  0x%x  %x" % (addr, self.functionSizes[addr], self.functionHashes[addr]))
            if self.functionHashes[addr] in self.baseQ3FunctionRevHashes:
                output("\tpossible match to")
                for n in self.baseQ3FunctionRevHashes[self.functionHashes[addr]]:
                    output(" %s" % n)
            output("\n")
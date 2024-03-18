import re
import glob
from pathlib import Path
from typing import List, Dict, Tuple, Union, Optional

"""

This is super limited. It does not actually view the code as an AST and
instead just reads line by line to find required keywords. This is only
temporary until I've finished the AST GBuild C# implementation.

Problems:
    - Massively format dependent (since it reads line by line).
    - Does not allow for accessor comments.
    - Spaces within an accessor type require the "-" special type at the end since otherwise its parsed incorrectly.
    - Reads classObject as literal string, does not handle var reassignment etc.

"""

ACCESSOR_SPECIAL_TYPES = {
    "default": {
        "set": True,
        "get": True,
        "is": False
    },
    "readonly": {
        "set": False,
        "get": True,
        "is": False
    },
    "is": {
        "set": True,
        "get": False,
        "is": True
    }
}

ACCESSOR_METHODS = {
    "set": [
        "@param value %TYPE%",
        "@return self",
        "value"
    ],
    "get": [
        "@param fallback? any Optional fallback to return if value is nil.",
        "@return %TYPE%",
        "fallback"
    ],
    "is": [
        None,
        "@return boolean",
        None
    ]
}

PATTERN = re.compile("\\W")


class AccessorFuncParser:
    LINES: List[str] = []

    def __init__(self, text: Union[str, List[str]]):
        self.LINES = text if isinstance(text, list) else text.split("\n")

    # Find all commented class names and their associated object names.
    def findClasses(self) -> List[tuple]:

        classDefinitionPositions = []
        for i, line in enumerate(self.LINES):
            if not line.startswith("---@class"):
                continue

            # Class comment was found.
            parts = line.split(" ")
            if len(parts) == 0:
                continue

            # Remove trailing colon used for class inheritance.
            className = parts[1]
            if className[-1] == ":":
                className = className[:-1]

            classDefinitionPositions.append(
                (i, className)
            )

        # If no classes were found, return.
        if len(classDefinitionPositions) == 0:
            return []

        # Now the class comments have been found, we need to find the name of the actual object variable.
        classes = []
        for definition in classDefinitionPositions:

            startPos = definition[0] + 1
            for i, line in enumerate(self.LINES[startPos:]):
                if line[:2] in ["--", "//"]:
                    continue

                # This is the first non-comment after the class definition. It should therefore be the class object.
                if "=" not in line:
                    print(f"{definition[1]} is missing any valid class object assigment #{startPos + i}!")
                    continue

                parts = line.split(" ")
                classes.append((
                    parts[parts.index("=") - 1].strip(),  # ObjectName
                    definition[1],  # ClassName
                ))
                break

        return classes if len(classes) > 0 else None

    # Parse a found ClassAccessorFunc call structure.
    def _parseAccessorCall(self, objectName: str, pos: int) -> Dict[str, Tuple[str, Dict[str, bool]]]:

        # Check if accessors have been disabled for this call.
        if "---@accessors-disabled" in self.LINES[pos]:
            return {}

        # Find all lines within the ClassAccessorFunc call.
        accessors, startPos, tableDepth = {}, pos + 1, 0
        for i, line in enumerate(self.LINES[startPos:]):

            # Invalid line / Closing table.
            if len(line) == 0 or line[0] == "}":
                break

            # Very dirty code to make sure it still supports nested tables within the AccessorTable.
            # This could be inside some validator function implementation etc.
            if tableDepth > 0:
                if "{" in line:
                    tableDepth += 1

                if "}" in line:
                    tableDepth -= 1
                    if 0 > tableDepth:
                        tableDepth = 0

                continue

            # Make sure the line actually has an assigment and accessor definition.
            line = line.strip()
            if "=" not in line or "---@accessor " not in line:
                print(f"Object '{objectName}' ClassAccessorFunc looks invalid on line #{startPos + i}!", line)
                break

            # Read accessor key and type from line.
            accessorKey = line[:line.find("=")].strip()
            commentStart = line.find("---@accessor")
            accessorType = line[commentStart + 13:].strip()  # Offset by string size to get start of actual typedef.
            accessors[accessorKey] = accessorType

            # Check to see if we're opening an unclosed table here. This is because ClassAccessorFunc
            # just accepts structured tables, so sometimes you may want to supply the table directly.
            tableClosed = "}" in line and commentStart > line.find("}")
            if "{" in line and not tableClosed:
                tableDepth += 1

            elif tableClosed and tableDepth > 0:
                tableDepth -= 1

        return accessors

    # Find and parse all ClassAccessorFunc calls within the lines.
    def findAccessors(self) -> dict:

        # Find accessor func calls.
        objectAccessors = {}
        for i, line in enumerate(self.LINES):
            if not line.startswith("ClassAccessorFunc("):
                continue

            # Found a ClassAccessorFunc call!
            objectName = line[18:line.find(",")]
            if objectName not in objectAccessors:
                objectAccessors[objectName] = {}

            for k, v in self._parseAccessorCall(objectName, i).items():
                objectAccessors[objectName][k] = v

        return objectAccessors


class AccessorFuncGenerator:

    # Get accessor methods from provided type string.
    @staticmethod
    def _GetAccessorTypeMethods(accessorType: str) -> Optional[Tuple[str, Dict[str, bool]]]:

        accessorSet = ACCESSOR_SPECIAL_TYPES["default"]

        # Check to see if the type is specifying a special set.
        # The "-" special type is a really lazy fix since I just realised types with spaces such as: "table<number, string>"
        # contains spaces therefore it's recognised as having a special type. Instead of actually fixing this by handling
        # opened spans, just use a minus sign to signify "ignore".
        parts = accessorType.split(" ")
        if len(parts) > 1 and parts[-1] != "-":

            if parts[-1] not in ACCESSOR_SPECIAL_TYPES:
                return None

            accessorSet = ACCESSOR_SPECIAL_TYPES[parts[-1]]

        return " ".join(parts[:-1]) if len(parts) > 1 else parts[0], accessorSet

    @staticmethod
    def ToLuaFile(className: str, accessors: dict) -> Tuple[str, str]:

        objectName = re.sub(PATTERN, "", className)
        code = [
            "---@meta\n",
            "---@class " + className,
            "local " + objectName + " = {}\n"
        ]
        for accessorName, accessorData in accessors.items():

            # Add all enabled accessor methods.
            accessorBlock = []
            for methodName, methodEnabled in accessorData[1].items():
                if not methodEnabled:
                    continue

                # Get info about the accessor method.
                accessorMethodTypeData = ACCESSOR_METHODS.get(methodName)
                if accessorMethodTypeData is None:
                    continue

                # Get docs and argument from accessor method.
                paramDoc, returnDoc, argument = accessorMethodTypeData
                for doc in [paramDoc, returnDoc]:
                    if doc is not None:
                        accessorBlock.append("---" + doc.replace("%TYPE%", accessorData[0]))

                accessorBlock.append(
                    f"function {objectName}:{methodName.capitalize()}{accessorName}({argument if argument is not None else ''}) end\n",
                )

            code.extend([
                "\n".join(accessorBlock),
            ])

        return objectName, "\n".join(code)

    @classmethod
    def Parse(cls, code: Union[str, List[str]]) -> Dict[str, Dict[str, Tuple[str, Dict[str, bool]]]]:

        parser = AccessorFuncParser(code)

        # Get all ClassAccessorFunc calls in file.
        accessors = parser.findAccessors()
        if len(accessors) == 0:
            return {}

        output = {}
        for classData in parser.findClasses():

            objectName, className = classData
            if objectName not in accessors:
                continue

            # Here, we've got a class with accessor(s).
            accessorMethods = {}
            for key, typeStr in accessors[objectName].items():

                methods = cls._GetAccessorTypeMethods(typeStr)
                if methods is None:
                    print(f"Invalid special accessor type '{key}' for '{className}' ('{objectName}')!")
                    continue

                accessorMethods[key] = methods

            # Merge collected accessor methods with existing for class.
            if className not in output:
                output[className] = accessorMethods

            else:
                for k, v in accessorMethods.items():
                    output[className][k] = v

        return output

    @classmethod
    def ParseDirectory(cls, path: str) -> Dict[str, Dict[str, Tuple[str, Dict[str, bool]]]]:

        allClasses = {}
        for file in glob.glob(path + "/**/*.lua", recursive=True):

            try:
                with open(file, "r", encoding="utf8") as fp:
                    lines = fp.read().splitlines()

                if lines is None:
                    raise Exception("Failed to read file lines for seemingly no reason?")

            except Exception as e:
                print(f"Failed to read '{file}' with error: {e}")
                continue

            for className, accessors in cls.Parse(lines).items():
                if className not in allClasses:
                    allClasses[className] = {}

                # Merge with existing dict.
                for k, v in accessors.items():
                    allClasses[className][k] = v

        return allClasses


if __name__ == "__main__":

    BASE_DIRECTORY = "D:\\GmodDevServer\\garrysmod\\gamemodes\\gnil"
    WRITE_DIRECTORY = BASE_DIRECTORY + "\\.build\\accessor-docs"

    # Make sure the write directory exists.
    Path(WRITE_DIRECTORY).mkdir(parents=True, exist_ok=True)

    # Create the lua file for each class file in directory.
    for fullClassName, classAccessors in AccessorFuncGenerator.ParseDirectory(BASE_DIRECTORY).items():

        cleanObjectName, metaLua = AccessorFuncGenerator.ToLuaFile(fullClassName, classAccessors)
        with open(WRITE_DIRECTORY + f"\\{cleanObjectName}.lua", "w+", encoding="utf8") as fp:
            fp.write(metaLua)

    print("Finished!")
    quit(0)

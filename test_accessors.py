from main import AccessorFuncGenerator, ACCESSOR_SPECIAL_TYPES


def test_AccessorFuncs():
    LUA = """
---@class ClassName
---...
local A = {
}
ClassAccessorFunc(A, {
    A = something.fn(), ---@accessor string
    B = something.fn(), ---@accessor number readonly
    C = something.fn()  ---@accessor boolean is
})
    """

    out = AccessorFuncGenerator.Parse(LUA)
    assert out["ClassName"] == {
        "A": ("string", ACCESSOR_SPECIAL_TYPES["default"]),
        "B": ("number", ACCESSOR_SPECIAL_TYPES["readonly"]),
        "C": ("boolean", ACCESSOR_SPECIAL_TYPES["is"])
    }


def test_MultipleAccessorCalls():
    LUA = """  
---@class OtherClass
local B = imaginaryFunction(
)
ClassAccessorFunc(B, {
    A = { ---@accessor imaginary
        {
            ...
        }
    },
    B = fn(), ---@accessor string
    C = {"var", FORCE_STRING} ---@accessor number
})
ClassAccessorFunc(C, {
    E = ... ---@accessor string
})
ClassAccessorFunc(B, {
    D = {"var", FORCE_NUMBER} ---@accessor Vector is
})  
    """

    out = AccessorFuncGenerator.Parse(LUA)
    assert out["OtherClass"] == {
        "A": ("imaginary", ACCESSOR_SPECIAL_TYPES["default"]),
        "B": ("string", ACCESSOR_SPECIAL_TYPES["default"]),
        "C": ("number", ACCESSOR_SPECIAL_TYPES["default"]),
        "D": ("Vector", ACCESSOR_SPECIAL_TYPES["is"])
    }
    assert "E" not in out["OtherClass"]


def test_MultipleClasses():
    LUA = """
---@class ClassA
local ClassA = {}
ClassAccessorFunc(ClassB, {
    A = "whatever", ---@accessor number
    B = "another" ---@accessor table<number, string[]> is
})

---@class ClassB
local ClassB = {}
ClassAccessorFunc(ClassA, {
    C = "something", ---@accessor string
    D = "final" ---@accessor Player
})
    """

    out = AccessorFuncGenerator.Parse(LUA)
    assert out["ClassA"] == {
        "C": ("string", ACCESSOR_SPECIAL_TYPES["default"]),
        "D": ("Player", ACCESSOR_SPECIAL_TYPES["default"])
    }
    assert out["ClassB"] == {
        "A": ("number", ACCESSOR_SPECIAL_TYPES["default"]),
        "B": ("table<number, string[]>", ACCESSOR_SPECIAL_TYPES["is"])
    }


def test_DuplicateAccessors():
    LUA = """
---@class ClassA
local ClassA = {}
ClassAccessorFunc(ClassA, {
    A = "a", ---@accessor string
    B = "b"  ---@accessor Incorrect - is
})
ClassAccessorFunc(ClassB, {
    B = { ---@accessor AlsoIncorrect is
        {}
    }
})
ClassAccessorFunc(ClassA, {
    B = "b" ---@accessor Correct readonly
})

---@class ClassA
local CopyClassA = {}
ClassAccessorFunc(CopyClassA, {
    C = "c" ---@accessor number
})
    """

    out = AccessorFuncGenerator.Parse(LUA)
    assert out["ClassA"] == {
        "A": ("string", ACCESSOR_SPECIAL_TYPES["default"]),
        "B": ("Correct", ACCESSOR_SPECIAL_TYPES["readonly"]),
        "C": ("number", ACCESSOR_SPECIAL_TYPES["default"])
    }

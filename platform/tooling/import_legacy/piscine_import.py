"""Staged canonical piscine dataset import helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import shutil

import yaml

from platform_catalog import CatalogService, CatalogValidationError
from platform_grading import GradingEngine
from platform_grading.contracts import AttemptContext
from platform_scheduler import PoolEngineService, SessionExerciseRecord
from platform_sessions import PiscineSessionService


FIRST_PASS_TRACKS = (
    "shell00",
    "shell01",
    "c00",
    "c01",
    "c02",
    "c03",
    "c04",
    "c05",
    "c06",
)
REPOSITORY_C00_EXERCISES = ("ft_putchar", "ft_putstr")

LEGACY_TRACK_IMPORTS: dict[str, dict[str, str]] = {
    "c01": "LEGACY_C01_IMPORTS",
    "c02": "LEGACY_C02_IMPORTS",
    "c03": "LEGACY_C03_IMPORTS",
    "c04": "LEGACY_C04_IMPORTS",
    "c05": "LEGACY_C05_IMPORTS",
    "c06": "LEGACY_C06_IMPORTS",
}

LEGACY_C00_IMPORTS = {
    "ft_print_numbers": {
        "title": "ft_print_numbers",
        "summary": "Write a function that outputs the digits from 0 to 9.",
        "concepts": ["io", "iteration"],
        "skills": ["stdout", "loops"],
        "misconceptions": ["wrong_order", "extra_newline"],
        "estimated_minutes": 10,
        "difficulty": 1,
        "source_path": Path(
            "grademe 42 exam/n/success/ft_print_numbers/ft_print_numbers.c"
        ),
        "statement": (
            "# ft_print_numbers\n\n"
            "Write a function `ft_print_numbers` that prints the digits from `0` to `9` in ascending order.\n\n"
            "- Expected output: `0123456789`\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": "#include <unistd.h>\n\nvoid\tft_print_numbers(void)\n{\n}\n",
        "harness": (
            "#include <unistd.h>\n\n"
            "void\tft_print_numbers(void);\n\n"
            "int\tmain(void)\n{\n\tft_print_numbers();\n\treturn (0);\n}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "ascending_digits",
                    "expected_stdout": "0123456789",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                }
            ]
        },
        "compile_mode": "function_with_harness",
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "exact-order",
                    "prompt": "The digits must stay in ascending order from 0 through 9.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "no-trailing-newline",
                    "prompt": "Do not print an extra newline unless the exercise explicitly asks for it.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "loop-over-digits",
                    "prompt": "A small loop from the character '0' to '9' keeps the output compact and ordered.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Compare the observed stdout bytes against the exact 10-digit target string.",
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": False,
                },
            },
        },
    },
    "ft_countdown": {
        "title": "ft_countdown",
        "summary": "Write a program that outputs the digits from 9 to 0 followed by a newline.",
        "concepts": ["io", "iteration"],
        "skills": ["stdout", "main_program"],
        "misconceptions": ["missing_newline", "wrong_order"],
        "estimated_minutes": 10,
        "difficulty": 1,
        "source_path": Path("grademe 42 exam/n/success/ft_countdown/ft_countdown.c"),
        "statement": (
            "# ft_countdown\n\n"
            "Write a program that displays the digits from `9` to `0`, followed by a newline.\n\n"
            "- Expected output: `9876543210\\n`\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": ("#include <unistd.h>\n\nint\tmain(void)\n{\n\treturn (0);\n}\n"),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "countdown",
                    "expected_stdout": "9876543210\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                }
            ]
        },
        "compile_mode": "standalone_program",
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "newline-required",
                    "prompt": "This exercise does require a final newline after the last digit.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "descending-order",
                    "prompt": "The digits must be printed in descending order from 9 to 0.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "countdown-loop",
                    "prompt": "Start at the character '9' and move downward until you print '0'.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Observe whether the final byte is a newline and whether every digit appears exactly once.",
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": False,
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# C01 — string basics: ft_strlen, ft_strcpy (function_with_harness)
# ---------------------------------------------------------------------------
LEGACY_C01_IMPORTS = {
    "ft_strlen": {
        "title": "ft_strlen",
        "summary": "Write a function that returns the length of a string.",
        "concepts": ["strings", "iteration"],
        "skills": ["string_length", "loops"],
        "misconceptions": ["off_by_one", "counting_null_terminator"],
        "estimated_minutes": 10,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/4/ft_strlen/ft_strlen.c"
        ),
        "statement": (
            "# ft_strlen\n\n"
            "Write a function that returns the length of a string.\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nint\tft_strlen(char *str);\n```\n\n"
            "- Allowed functions: none\n"
        ),
        "starter": "int\tft_strlen(char *str)\n{\n\treturn (0);\n}\n",
        "harness": (
            "#include <stdio.h>\n\n"
            "int\t\tft_strlen(char *str);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            '\tprintf("%d\\n", ft_strlen(argv[1]));\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "empty_string",
                    "argv": [""],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "short_string",
                    "argv": ["abc"],
                    "expected_stdout": "3\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "long_string",
                    "argv": ["hello world"],
                    "expected_stdout": "11\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": [],
        "required_headers": [],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "empty-string",
                    "prompt": "An empty string has length 0 — make sure you handle it.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "null-terminator",
                    "prompt": "Do not count the null terminator as part of the length.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "walk-until-null",
                    "prompt": "Walk the string character by character until you hit '\\0'.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Compare the returned integer against the expected character count.",
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "ft_strcpy": {
        "title": "ft_strcpy",
        "summary": "Reproduce the behavior of the function strcpy.",
        "concepts": ["strings", "pointers"],
        "skills": ["string_copy", "pointer_arithmetic"],
        "misconceptions": ["forgetting_null_terminator", "off_by_one"],
        "estimated_minutes": 15,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/4/ft_strcpy/ft_strcpy.c"
        ),
        "statement": (
            "# ft_strcpy\n\n"
            "Reproduce the behavior of the function `strcpy` (man strcpy).\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nchar    *ft_strcpy(char *s1, char *s2);\n```\n\n"
            "- Allowed functions: none\n"
        ),
        "starter": "char\t*ft_strcpy(char *s1, char *s2)\n{\n\treturn (s1);\n}\n",
        "harness": (
            "#include <stdio.h>\n#include <string.h>\n\n"
            "char    *ft_strcpy(char *s1, char *s2);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\tchar buf[4096];\n"
            "\t(void)argc;\n"
            "\tmemset(buf, 0, sizeof(buf));\n"
            "\tft_strcpy(buf, argv[1]);\n"
            '\tprintf("%s\\n", buf);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "empty_string",
                    "argv": [""],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "short_string",
                    "argv": ["abc"],
                    "expected_stdout": "abc\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "spaces",
                    "argv": ["   c"],
                    "expected_stdout": "   c\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": [],
        "required_headers": [],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "null-terminator-copy",
                    "prompt": "Remember to copy the null terminator as well.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "return-value",
                    "prompt": "The function must return s1.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "copy-loop",
                    "prompt": "Copy characters one by one from s2 to s1, including the final '\\0'.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Compare the destination buffer content against the source string.",
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# C02 — string transformations: ulstr, repeat_alpha, search_and_replace
# ---------------------------------------------------------------------------
LEGACY_C02_IMPORTS = {
    "ulstr": {
        "title": "ulstr",
        "summary": "Write a program that reverses the case of every letter in a string.",
        "concepts": ["strings", "conditionals"],
        "skills": ["case_conversion", "argv_handling"],
        "misconceptions": ["forgetting_non_alpha", "wrong_argc_handling"],
        "estimated_minutes": 15,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/5/ulstr/ulstr.c"
        ),
        "statement": (
            "# ulstr\n\n"
            "Write a program that takes a string and reverses the case of all its letters.\n"
            "Other characters remain unchanged.\n\n"
            "You must display the result followed by a `\\n`.\n\n"
            "If the number of arguments is not 1, the program displays `\\n`.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "mixed_case",
                    "argv": ["aBcDeF"],
                    "expected_stdout": "AbCdEf\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "with_digits",
                    "argv": ["Hello 42!"],
                    "expected_stdout": "hELLO 42!\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "non-alpha-unchanged",
                    "prompt": "Non-alphabetical characters (digits, spaces, punctuation) stay unchanged.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "no-args-newline",
                    "prompt": "When no argument is given, just print a newline.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "ascii-offset",
                    "prompt": "The difference between 'A' and 'a' is 32. Add or subtract to swap case.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Check that every letter has its case flipped while non-letters remain identical."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "repeat_alpha": {
        "title": "repeat_alpha",
        "summary": "Write a program that repeats each letter by its alphabetical index.",
        "concepts": ["strings", "iteration", "conditionals"],
        "skills": ["char_arithmetic", "argv_handling"],
        "misconceptions": ["wrong_repeat_count", "case_sensitivity"],
        "estimated_minutes": 15,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/5/repeat_alpha/repeat_alpha.c"
        ),
        "statement": (
            "# repeat_alpha\n\n"
            "Write a program that takes a string and displays it repeating each alphabetical character\n"
            "as many times as its alphabetical index, followed by a newline.\n\n"
            "`'a'` becomes `'a'`, `'b'` becomes `'bb'`, `'e'` becomes `'eeeee'`, etc.\n"
            "Case remains unchanged.\n\n"
            "If the number of arguments is not 1, just display a newline.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["abc"],
                    "expected_stdout": "abbccc\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "with_non_alpha",
                    "argv": ["a 1b"],
                    "expected_stdout": "a 1bb\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "non-alpha-once",
                    "prompt": "Non-alphabetical characters are printed exactly once.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "case-preserving",
                    "prompt": "Uppercase 'A' has index 1 just like lowercase 'a'.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "alpha-index",
                    "prompt": "Subtract 'a' (or 'A') from the char to get a 0-based index, then add 1 for the repeat count.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Count repeated characters and verify each matches its alphabetical position."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "search_and_replace": {
        "title": "search_and_replace",
        "summary": "Write a program that replaces one character with another in a string.",
        "concepts": ["strings", "conditionals"],
        "skills": ["char_comparison", "argv_handling"],
        "misconceptions": ["wrong_argc_check", "replacing_multichar_args"],
        "estimated_minutes": 15,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/5/search_and_replace/search_and_replace.c"
        ),
        "statement": (
            "# search_and_replace\n\n"
            "Write a program that takes 3 arguments: a string, a character to find, and a replacement character.\n"
            "Replace every occurrence of the second argument in the first argument with the third argument.\n\n"
            "If the number of arguments is not 3, just display a newline.\n"
            "If the second or third argument is not a single character, display a newline.\n\n"
            "- Allowed functions: `write`, `exit`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "simple_replace",
                    "argv": ["hello", "l", "r"],
                    "expected_stdout": "herro\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_match",
                    "argv": ["zaz", "r", "u"],
                    "expected_stdout": "zaz\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "wrong_argc",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write", "exit"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "multi-char-args",
                    "prompt": "If the 2nd or 3rd argument is longer than one character, print just a newline.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "char-not-found",
                    "prompt": "If the search character is not in the string, print the original string unchanged.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "iterate-and-compare",
                    "prompt": "Walk the string; if current char matches the search char, print the replacement instead.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Compare each output character against the expected replacement."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# C03 — string parsing: first_word, rev_print, rot_13, rotone
# ---------------------------------------------------------------------------
LEGACY_C03_IMPORTS = {
    "first_word": {
        "title": "first_word",
        "summary": "Write a program that displays the first word of a string.",
        "concepts": ["strings", "parsing"],
        "skills": ["whitespace_handling", "argv_handling"],
        "misconceptions": ["not_skipping_leading_spaces", "including_tabs"],
        "estimated_minutes": 15,
        "difficulty": 3,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/6/first_word/first_word.c"
        ),
        "statement": (
            "# first_word\n\n"
            "Write a program that takes a string and displays its first word, followed by a newline.\n\n"
            "A word is a section of string delimited by spaces/tabs or by the start/end of the string.\n\n"
            "If the number of parameters is not 1, or if there are no words, simply display a newline.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["FOR PONY"],
                    "expected_stdout": "FOR\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "leading_spaces",
                    "argv": ["  lorem,ipsum  "],
                    "expected_stdout": "lorem,ipsum\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "leading-whitespace",
                    "prompt": "Skip leading spaces and tabs before the first word.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "only-spaces",
                    "prompt": "A string of only spaces/tabs should result in just a newline.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "two-loops",
                    "prompt": "Use one loop to skip whitespace, then another to print non-whitespace characters.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Verify only the first word appears in stdout, with no leading whitespace."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "rev_print": {
        "title": "rev_print",
        "summary": "Write a program that displays a string in reverse.",
        "concepts": ["strings", "iteration"],
        "skills": ["reverse_traversal", "string_length"],
        "misconceptions": ["off_by_one_at_end", "printing_null_terminator"],
        "estimated_minutes": 15,
        "difficulty": 3,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/7/rev_print/rev_print.c"
        ),
        "statement": (
            "# rev_print\n\n"
            "Write a program that takes a string, and displays the string in reverse\n"
            "followed by a newline.\n\n"
            "If the number of parameters is not 1, the program displays a newline.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "palindrome",
                    "argv": ["zaz"],
                    "expected_stdout": "zaz\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "normal",
                    "argv": ["abc"],
                    "expected_stdout": "cba\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "empty-string",
                    "prompt": "An empty string should produce only a newline.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "single-char",
                    "prompt": "A single character reversed is itself.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "strlen-then-backwards",
                    "prompt": "Find the string length first, then print characters from the last to the first.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Read the output backwards and verify it matches the input."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "rotone": {
        "title": "rotone",
        "summary": "Write a program that shifts every letter by one position in the alphabet.",
        "concepts": ["strings", "conditionals"],
        "skills": ["char_arithmetic", "modular_wrap"],
        "misconceptions": ["forgetting_z_wrap", "modifying_non_alpha"],
        "estimated_minutes": 15,
        "difficulty": 3,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/7/rotone/rotone.c"
        ),
        "statement": (
            "# rotone\n\n"
            "Write a program that takes a string and displays it, replacing each of its\n"
            "letters by the next one in alphabetical order.\n\n"
            "`'z'` becomes `'a'` and `'Z'` becomes `'A'`. Case remains unaffected.\n\n"
            "The output will be followed by a `\\n`.\n"
            "If the number of arguments is not 1, the program displays `\\n`.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["abc"],
                    "expected_stdout": "bcd\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "wrap_z",
                    "argv": ["zZ"],
                    "expected_stdout": "aA\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "z-wraps-to-a",
                    "prompt": "'z' wraps to 'a' and 'Z' wraps to 'A'.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "non-alpha-unchanged",
                    "prompt": "Digits, spaces, and punctuation stay unchanged.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "check-z-boundary",
                    "prompt": "Check if the character is 'z' or 'Z' before adding 1; if so, wrap to 'a' or 'A'.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Verify each output letter is exactly one position ahead, with z/Z wrapping."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "rot_13": {
        "title": "rot_13",
        "summary": "Write a program that applies ROT13 encoding to a string.",
        "concepts": ["strings", "conditionals"],
        "skills": ["char_arithmetic", "modular_wrap"],
        "misconceptions": ["wrong_rotation_direction", "modifying_non_alpha"],
        "estimated_minutes": 15,
        "difficulty": 3,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/7/rot_13/rot_13.c"
        ),
        "statement": (
            "# rot_13\n\n"
            "Write a program that takes a string and displays it, replacing each of its\n"
            "letters by the letter 13 spaces ahead in alphabetical order.\n\n"
            "`'z'` becomes `'m'` and `'Z'` becomes `'M'`. Case remains unaffected.\n\n"
            "The output will be followed by a `\\n`.\n"
            "If the number of arguments is not 1, the program displays `\\n`.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": (
            "#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n"
            "{\n"
            "\t(void)argc;\n"
            "\t(void)argv;\n"
            '\twrite(1, "\\n", 1);\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["abc"],
                    "expected_stdout": "nop\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "sentence",
                    "argv": ["Hello World"],
                    "expected_stdout": "Uryyb Jbeyq\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "no_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "rot13-involution",
                    "prompt": "ROT13 applied twice returns the original text.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "non-alpha-unchanged",
                    "prompt": "Non-alphabetical characters stay unchanged.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "split-alphabet",
                    "prompt": "Letters A-M (a-m) shift forward by 13; letters N-Z (n-z) shift backward by 13.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Apply ROT13 mentally to each input letter and compare with output."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# C04 — number-string conversions: ft_atoi, ft_itoa, ft_atoi_base
# ---------------------------------------------------------------------------
LEGACY_C04_IMPORTS = {
    "ft_atoi": {
        "title": "ft_atoi",
        "summary": "Write a function that converts a string to an integer.",
        "concepts": ["strings", "parsing", "math"],
        "skills": ["string_to_int"],
        "misconceptions": ["overflow", "multiple_signs_handling"],
        "estimated_minutes": 20,
        "difficulty": 4,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_02/4/ft_atoi/ft_atoi.c"
        ),
        "statement": (
            "# ft_atoi\n\n"
            "Write a function that converts the string argument str to an integer (type int) and returns it.\n\n"
            "It works much like the standard atoi(const char *str) function, see the man.\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nint\tft_atoi(const char *str);\n```\n\n"
            "- Allowed functions: none\n"
        ),
        "starter": "int\tft_atoi(const char *str)\n{\n\treturn (0);\n}\n",
        "harness": (
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n\n"
            "int\tft_atoi(const char *str);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\tif (argc == 2)\n"
            '\t\tprintf("%d\\n", ft_atoi(argv[1]));\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "simple_positive",
                    "argv": ["42"],
                    "expected_stdout": "42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "simple_negative",
                    "argv": ["-42"],
                    "expected_stdout": "-42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "whitespace",
                    "argv": [" \\t\\n\\v\\f\\r 42"],
                    "expected_stdout": "42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "multiple_signs",
                    "argv": ["--42"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "max_int",
                    "argv": ["2147483647"],
                    "expected_stdout": "2147483647\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "min_int",
                    "argv": ["-2147483648"],
                    "expected_stdout": "-2147483648\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": [],
        "required_headers": [],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "whitespace",
                    "prompt": "Handle leading whitespace correctly according to man atoi.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "single_sign",
                    "prompt": "Only one sign should be parsed; subsequent signs break the number.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "skip_whitespace",
                    "prompt": "Use a while loop to skip space, '\\t', '\\n', '\\v', '\\f', and '\\r'.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Make sure multiple signs result in 0 or stop parsing immediately."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "ft_itoa": {
        "title": "ft_itoa",
        "summary": "Write a function that converts an integer to a string.",
        "concepts": ["strings", "formatting", "memory", "math"],
        "skills": ["int_to_string", "malloc"],
        "misconceptions": ["int_min_handling"],
        "estimated_minutes": 25,
        "difficulty": 4,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_04/2/ft_itoa/ft_itoa.c"
        ),
        "statement": (
            "# ft_itoa\n\n"
            "Write a function that takes an int and converts it to a null-terminated string.\n"
            "The function returns the result in a char array that you must allocate.\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nchar\t*ft_itoa(int nbr);\n```\n\n"
            "- Allowed functions: `malloc`\n"
        ),
        "starter": "char\t*ft_itoa(int nbr)\n{\n\treturn (0);\n}\n",
        "harness": (
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n\n"
            "char\t*ft_itoa(int nbr);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\tif (argc == 2)\n"
            "\t{\n"
            "\t\tchar *res = ft_itoa(atoi(argv[1]));\n"
            '\t\tprintf("%s\\n", res);\n'
            "\t\tfree(res);\n"
            "\t}\n"
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "simple_positive",
                    "argv": ["42"],
                    "expected_stdout": "42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "simple_negative",
                    "argv": ["-42"],
                    "expected_stdout": "-42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "zero",
                    "argv": ["0"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "max_int",
                    "argv": ["2147483647"],
                    "expected_stdout": "2147483647\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "min_int",
                    "argv": ["-2147483648"],
                    "expected_stdout": "-2147483648\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": ["malloc"],
        "required_headers": ["stdlib.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "int-min",
                    "prompt": "INT_MIN cannot be made positive by multiplying by -1. You must handle it safely.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "count-digits",
                    "prompt": "You may need to figure out how many digits long the int is before malloc'ing.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Be careful with memory allocation size and negative sign space."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "ft_atoi_base": {
        "title": "ft_atoi_base",
        "summary": "Write a function that converts a string in a given base to an integer.",
        "concepts": ["strings", "parsing", "math", "bases"],
        "skills": ["base_conversion"],
        "misconceptions": ["case_sensitivity", "sign_handling"],
        "estimated_minutes": 25,
        "difficulty": 4,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_03/3/ft_atoi_base/ft_atoi_base.c"
        ),
        "statement": (
            "# ft_atoi_base\n\n"
            "Write a function that converts the string argument str (base N <= 16) to an integer (base 10) and returns it.\n\n"
            "The characters recognized in the base are: 0123456789abcdef\n"
            'Those are, of course, to be trimmed according to the requested base. For example, base 4 recognizes "0123" and base 16 recognizes "0123456789abcdef".\n\n'
            'Uppercase letters must also be recognized: "12fdb3" is the same as "12FDB3".\n\n'
            "Minus signs ('-') are interpreted only if they are the first character of the string.\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nint\tft_atoi_base(const char *str, int str_base);\n```\n\n"
            "- Allowed functions: none\n"
        ),
        "starter": "int\tft_atoi_base(const char *str, int str_base)\n{\n\treturn (0);\n}\n",
        "harness": (
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n\n"
            "int\tft_atoi_base(const char *str, int str_base);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\tif (argc == 3)\n"
            "\t{\n"
            '\t\tprintf("%d\\n", ft_atoi_base(argv[1], atoi(argv[2])));\n'
            "\t}\n"
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["12fdb3", "16"],
                    "expected_stdout": "1244595\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "upper",
                    "argv": ["12FDB3", "16"],
                    "expected_stdout": "1244595\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "binary",
                    "argv": ["101010", "2"],
                    "expected_stdout": "42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "negative",
                    "argv": ["-2A", "16"],
                    "expected_stdout": "-42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": [],
        "required_headers": [],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "case-insensitive",
                    "prompt": "Base letters can be uppercase or lowercase.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "char-value",
                    "prompt": "Create a helper function to determine the integer value of a character if it's within the given base.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Ensure negative sign triggers negative accumulation only at the start."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# C05 — math functions: is_power_of_2, pgcd, lcm, add_prime_sum
# ---------------------------------------------------------------------------
LEGACY_C05_IMPORTS = {
    "is_power_of_2": {
        "title": "is_power_of_2",
        "summary": "Write a function that determines if a given number is a power of 2.",
        "concepts": ["math", "binary"],
        "skills": ["powers", "modulo"],
        "misconceptions": ["zero", "odd_numbers"],
        "estimated_minutes": 15,
        "difficulty": 3,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_03/1/is_power_of_2/is_power_of_2.c"
        ),
        "statement": (
            "# is_power_of_2\n\n"
            "Write a function that determines if a given number is a power of 2.\n\n"
            "This function returns 1 if the given number is a power of 2, otherwise it returns 0.\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nint\tis_power_of_2(unsigned int n);\n```\n\n"
            "- Allowed functions: none\n"
        ),
        "starter": "int\tis_power_of_2(unsigned int n)\n{\n\treturn (0);\n}\n",
        "harness": (
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n\n"
            "int\tis_power_of_2(unsigned int n);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\tif (argc == 2)\n"
            '\t\tprintf("%d\\n", is_power_of_2(atoi(argv[1])));\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "two",
                    "argv": ["2"],
                    "expected_stdout": "1\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "1",
                    "argv": ["1"],
                    "expected_stdout": "1\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "0",
                    "argv": ["0"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "non_power",
                    "argv": ["42"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "power",
                    "argv": ["1024"],
                    "expected_stdout": "1\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": [],
        "required_headers": [],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "zero",
                    "prompt": "0 is not a power of 2.",
                    "reveal_before_submit": True,
                },
                {
                    "id": "one",
                    "prompt": "1 is a power of 2 (2^0).",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "modulo-2",
                    "prompt": "Keep dividing by 2 as long as n > 0 and n % 2 == 0.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "There is also a very elegant bitwise trick for this: `(n & (n - 1)) == 0`"
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "pgcd": {
        "title": "pgcd",
        "summary": "Write a program that displays the highest common denominator of two positive integers.",
        "concepts": ["math", "division"],
        "skills": ["hcf"],
        "misconceptions": [],
        "estimated_minutes": 20,
        "difficulty": 4,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_03/2/pgcd/pgcd.c"
        ),
        "statement": (
            "# pgcd\n\n"
            "Write a program that takes two strings representing two strictly positive integers that fit in an int.\n\n"
            "Display their highest common denominator followed by a newline (It's always a strictly positive integer).\n\n"
            "If the number of parameters is not 2, display a newline.\n\n"
            "- Allowed functions: `printf`, `atoi`, `malloc`, `free`\n"
        ),
        "starter": '#include <stdio.h>\n#include <stdlib.h>\n\nint\tmain(int argc, char **argv)\n{\n\t(void)argc;\n\t(void)argv;\n\n\tprintf("\\n");\n\treturn (0);\n}\n',
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["42", "10"],
                    "expected_stdout": "2\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "different",
                    "argv": ["42", "12"],
                    "expected_stdout": "6\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "large",
                    "argv": ["14", "77"],
                    "expected_stdout": "7\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "one_arg",
                    "argv": ["17"],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["printf", "atoi", "malloc", "free"],
        "required_headers": ["stdio.h", "stdlib.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "no-args-newline",
                    "prompt": "Incorrect args means output a newline.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "find-largest",
                    "prompt": "Start from the smaller of the two numbers and walk down, checking if it divides both.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Pay attention to your edge case logic handling missing arguments."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "lcm": {
        "title": "lcm",
        "summary": "Write a function that returns the lowest common multiple of two positive integers.",
        "concepts": ["math", "division"],
        "skills": ["lcm"],
        "misconceptions": [],
        "estimated_minutes": 20,
        "difficulty": 4,
        "source_path": Path("grademe-main/.subjects/PISCINE_PART/exam_03/3/lcm/lcm.c"),
        "statement": (
            "# lcm\n\n"
            "Write a function who takes two unsigned int as parameters and returns the computed LCM of those parameters.\n\n"
            "LCM (Lowest Common Multiple) of two non-zero integers is the smallest positive integer divisible by the both of them.\n\n"
            "A LCM can be calculated in two ways:\n"
            "- You can calculate every multiples of each integers until you have a common multiple other than 0\n"
            "- You can use the HCF (Highest Common Factor) of these two integers and calculate as follows:\n\n"
            "\tLCM(x, y) = | x * y | / HCF(x, y)\n\n"
            '| x * y | means "Absolute value of the product of x by y"\n\n'
            "If at least one integer is null, LCM is equal to 0.\n\n"
            "Your function must be declared as follows:\n\n"
            "```c\nunsigned int\tlcm(unsigned int a, unsigned int b);\n```\n\n"
            "- Allowed functions: none\n"
        ),
        "starter": "unsigned int\tlcm(unsigned int a, unsigned int b)\n{\n\treturn (0);\n}\n",
        "harness": (
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n\n"
            "unsigned int\tlcm(unsigned int a, unsigned int b);\n\n"
            "int main(int argc, char **argv)\n"
            "{\n"
            "\tif (argc == 3)\n"
            '\t\tprintf("%u\\n", lcm(atoi(argv[1]), atoi(argv[2])));\n'
            "\treturn (0);\n"
            "}\n"
        ),
        "tests": {
            "cases": [
                {
                    "id": "simple",
                    "argv": ["42", "10"],
                    "expected_stdout": "210\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "1",
                    "argv": ["1", "42"],
                    "expected_stdout": "42\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "zero",
                    "argv": ["0", "42"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "large",
                    "argv": ["14", "77"],
                    "expected_stdout": "154\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "function_with_harness",
        "allowed_functions": [],
        "required_headers": [],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "zero",
                    "prompt": "If one of the inputs is 0, the LCM is 0.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "start-large",
                    "prompt": "Start checking multiples from the maximum of `a` and `b`.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": ["Ensure performance is fast even for 1 and large numbers."],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "add_prime_sum": {
        "title": "add_prime_sum",
        "summary": "Write a program that takes a positive integer as argument and displays the sum of all prime numbers inferior or equal to it.",
        "concepts": ["math", "division", "primes", "io"],
        "skills": ["putnbr_recursive", "finding_primes"],
        "misconceptions": ["0_and_1_arent_primes"],
        "estimated_minutes": 30,
        "difficulty": 4,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_03/2/add_prime_sum/add_prime_sum.c"
        ),
        "statement": (
            "# add_prime_sum\n\n"
            "Write a program that takes a positive integer as argument and displays the sum of all prime numbers inferior or equal to it followed by a newline.\n\n"
            "If the number of arguments is not 1, or if the argument is not a positive number, just display 0 followed by a newline.\n\n"
            "Yes, the exercises are strictly in C language, so you MUST write a function that formats int to chars using `write` instead of `printf`.\n\n"
            "- Allowed functions: `write`, `exit`\n"
        ),
        "starter": '#include <unistd.h>\n\nint\tmain(int argc, char **argv)\n{\n\t(void)argc;\n\t(void)argv;\n\twrite(1, "0\\n", 2);\n\treturn (0);\n}\n',
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "five",
                    "argv": ["5"],
                    "expected_stdout": "10\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "seven",
                    "argv": ["7"],
                    "expected_stdout": "17\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "nine",
                    "argv": ["9"],
                    "expected_stdout": "17\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "one",
                    "argv": ["1"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "zero",
                    "argv": ["0"],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "missing_args",
                    "argv": [],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write", "exit"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "one-is-not-prime",
                    "prompt": "1 is not technically considered a prime number, so do not include it.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "putnbr",
                    "prompt": "You need a function like `putnbr(int)` to print the result since printf is disallowed.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Sum all primes recursively or iteratively, verify correctly outputted digits."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# C06 — argv arguments: aff_first_param, aff_last_param, paramsum
# ---------------------------------------------------------------------------
LEGACY_C06_IMPORTS = {
    "aff_first_param": {
        "title": "aff_first_param",
        "summary": "Write a program that takes strings as arguments, and displays its first argument.",
        "concepts": ["argv", "main_program"],
        "skills": ["command_line_args"],
        "misconceptions": ["argv0_is_program_name"],
        "estimated_minutes": 10,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/2/aff_first_param/aff_first_param.c"
        ),
        "statement": (
            "# aff_first_param\n\n"
            "Write a program that takes strings as arguments, and displays its first argument followed by a \\n.\n\n"
            "If the number of arguments is less than 1, the program displays \\n.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": '#include <unistd.h>\n\nint\tmain(int argc, char **argv)\n{\n\t(void)argc;\n\t(void)argv;\n\n\twrite(1, "\\n", 1);\n\treturn (0);\n}\n',
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "one_arg",
                    "argv": ["hello"],
                    "expected_stdout": "hello\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "multiple",
                    "argv": ["hello", "world", "you"],
                    "expected_stdout": "hello\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "missing_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "missing-args-newline",
                    "prompt": "If no arguments are provided to the program, it must display a newline.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "argv1",
                    "prompt": "Remember argv[0] is the name of the executable. Your target is argv[1].",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": ["Verify argv extraction bounds checks prevent segfaults."],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "aff_last_param": {
        "title": "aff_last_param",
        "summary": "Write a program that takes strings as arguments, and displays its last argument.",
        "concepts": ["argv", "main_program"],
        "skills": ["command_line_args"],
        "misconceptions": ["argv_count"],
        "estimated_minutes": 10,
        "difficulty": 2,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_01/2/aff_last_param/aff_last_param.c"
        ),
        "statement": (
            "# aff_last_param\n\n"
            "Write a program that takes strings as arguments, and displays its last argument followed by a \\n.\n\n"
            "If the number of arguments is less than 1, the program displays \\n.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": '#include <unistd.h>\n\nint\tmain(int argc, char **argv)\n{\n\t(void)argc;\n\t(void)argv;\n\n\twrite(1, "\\n", 1);\n\treturn (0);\n}\n',
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "one_arg",
                    "argv": ["hello"],
                    "expected_stdout": "hello\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "multiple",
                    "argv": ["hello", "world", "you"],
                    "expected_stdout": "you\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "missing_args",
                    "argv": [],
                    "expected_stdout": "\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "missing-args-newline",
                    "prompt": "If no arguments are provided to the program, it must display a newline.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "argc-minus-1",
                    "prompt": "Remember argv[0] is the executable name, and argc reflects this. Use argv[argc - 1].",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": ["Verify argc is properly offset."],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
    "paramsum": {
        "title": "paramsum",
        "summary": "Write a program that displays the number of arguments passed to it.",
        "concepts": ["argv", "main_program", "io"],
        "skills": ["command_line_args", "putnbr_recursive"],
        "misconceptions": [],
        "estimated_minutes": 20,
        "difficulty": 3,
        "source_path": Path(
            "grademe-main/.subjects/PISCINE_PART/exam_03/3/paramsum/paramsum.c"
        ),
        "statement": (
            "# paramsum\n\n"
            "Write a program that displays the number of arguments passed to it, followed by a newline.\n\n"
            "If there are no arguments, just display a 0 followed by a newline.\n\n"
            "- Allowed functions: `write`\n"
        ),
        "starter": '#include <unistd.h>\n\nint\tmain(int argc, char **argv)\n{\n\t(void)argc;\n\t(void)argv;\n\n\twrite(1, "0\\n", 2);\n\treturn (0);\n}\n',
        "harness": None,
        "tests": {
            "cases": [
                {
                    "id": "missing_args",
                    "argv": [],
                    "expected_stdout": "0\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "one_arg",
                    "argv": ["hello"],
                    "expected_stdout": "1\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
                {
                    "id": "multiple",
                    "argv": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"],
                    "expected_stdout": "11\n",
                    "expected_stderr": "",
                    "expected_exit_code": 0,
                },
            ]
        },
        "compile_mode": "standalone_program",
        "allowed_functions": ["write"],
        "required_headers": ["unistd.h"],
        "learning": {
            "visible_edge_cases": [
                {
                    "id": "many-args",
                    "prompt": "If there are more than 9 arguments, you will need to print a multi-digit number.",
                    "reveal_before_submit": True,
                },
            ],
            "hints": [
                {
                    "id": "recursive-putnbr",
                    "prompt": "You'll need a way to output digits, such as a recursive put_number function or iterative write.",
                    "unlock_after_attempts": 1,
                }
            ],
            "observation": {
                "enabled": True,
                "prompts": [
                    "Make sure the displayed number correctly represents the number of external args (not counting the program name itself)."
                ],
                "capture": {
                    "stdout_preview": True,
                    "stdin_echo": False,
                    "argv_echo": True,
                },
            },
        },
    },
}


@dataclass(slots=True)
class PiscineSourceInventory:
    track: str
    source_id: str
    source_kind: str
    root_path: str
    discovered_candidates: int
    importable_candidates: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "track": self.track,
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "root_path": self.root_path,
            "discovered_candidates": self.discovered_candidates,
            "importable_candidates": self.importable_candidates,
            "notes": self.notes,
        }


@dataclass(slots=True)
class PiscineImportedExercise:
    exercise_id: str
    track: str
    source_id: str
    source_kind: str
    origin_path: str
    runtime_ready: bool
    canonical_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "exercise_id": self.exercise_id,
            "track": self.track,
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "origin_path": self.origin_path,
            "runtime_ready": self.runtime_ready,
            "canonical_path": self.canonical_path,
        }


@dataclass(slots=True)
class PiscinePoolRecord:
    pool_id: str
    track: str
    canonical_path: str
    exercise_count: int
    runtime_ready: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "pool_id": self.pool_id,
            "track": self.track,
            "canonical_path": self.canonical_path,
            "exercise_count": self.exercise_count,
            "runtime_ready": self.runtime_ready,
        }


@dataclass(slots=True)
class PiscineValidationSummary:
    catalog_valid: bool
    pool_valid: bool
    candidate_resolution_valid: bool
    session_progression_valid: bool
    session_progression_order: list[str] = field(default_factory=list)
    graded_exercises: list[dict[str, object]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "catalog_valid": self.catalog_valid,
            "pool_valid": self.pool_valid,
            "candidate_resolution_valid": self.candidate_resolution_valid,
            "session_progression_valid": self.session_progression_valid,
            "session_progression_order": self.session_progression_order,
            "graded_exercises": self.graded_exercises,
            "notes": self.notes,
        }


@dataclass(slots=True)
class PiscineDatasetImportReport:
    generated_at: str
    staging_root: str
    repository_root: str
    sources: list[PiscineSourceInventory]
    imported_exercises: list[PiscineImportedExercise]
    imported_pools: list[PiscinePoolRecord]
    missing_or_incomplete: list[dict[str, object]]
    unresolved_migration_gaps: list[str]
    validation: PiscineValidationSummary

    def to_dict(self) -> dict[str, object]:
        discovered_counts = Counter(item.track for item in self.sources)
        imported_counts = Counter(item.track for item in self.imported_exercises)
        pool_counts = Counter(item.track for item in self.imported_pools)
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "repository_root": self.repository_root,
            "summary": {
                "discovered_source_counts": dict(sorted(discovered_counts.items())),
                "imported_canonical_exercise_counts": dict(
                    sorted(imported_counts.items())
                ),
                "imported_pool_counts": dict(sorted(pool_counts.items())),
                "missing_or_incomplete_count": len(self.missing_or_incomplete),
                "unresolved_gap_count": len(self.unresolved_migration_gaps),
                "catalog_valid": self.validation.catalog_valid,
                "pool_valid": self.validation.pool_valid,
                "candidate_resolution_valid": self.validation.candidate_resolution_valid,
                "session_progression_valid": self.validation.session_progression_valid,
            },
            "sources": [item.to_dict() for item in self.sources],
            "imported_exercises": [item.to_dict() for item in self.imported_exercises],
            "imported_pools": [item.to_dict() for item in self.imported_pools],
            "missing_or_incomplete": self.missing_or_incomplete,
            "unresolved_migration_gaps": self.unresolved_migration_gaps,
            "validation": self.validation.to_dict(),
        }


class PiscineDatasetImportService:
    """Stage and validate the first canonical piscine dataset import pass."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.generated_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @property
    def platform_root(self) -> Path:
        return self.workspace_root / "platform"

    @property
    def canonical_exercises_root(self) -> Path:
        return self.platform_root / "datasets/exercises/piscine"

    @property
    def canonical_pools_root(self) -> Path:
        return self.platform_root / "datasets/pools/piscine"

    @property
    def staging_root(self) -> Path:
        return (
            self.platform_root
            / "runtime/staging/import_legacy/latest/piscine_import/latest"
        )

    @property
    def accepted_root(self) -> Path:
        return self.staging_root / "accepted"

    @property
    def repository_root(self) -> Path:
        return self.staging_root / "repository_root"

    @property
    def reports_root(self) -> Path:
        return self.staging_root / "reports"

    @property
    def report_path(self) -> Path:
        return self.reports_root / "piscine_import.latest.yml"

    @property
    def status_path(self) -> Path:
        return self.workspace_root / "PISCINE_DATASET_STATUS.md"

    def discover_sources(self) -> list[PiscineSourceInventory]:
        inventories: list[PiscineSourceInventory] = []
        for track in FIRST_PASS_TRACKS:
            root = self.workspace_root / "ecosystem/piscine" / track
            inventories.append(
                PiscineSourceInventory(
                    track=track,
                    source_id=f"ecosystem:{track}",
                    source_kind="ecosystem_placeholder",
                    root_path=str(root),
                    discovered_candidates=0,
                    importable_candidates=0,
                    notes=["directory exists but contains no runtime bundle files"]
                    if root.exists()
                    else ["source root missing"],
                )
            )

        c00_root = self.canonical_exercises_root / "c00"
        inventories.append(
            PiscineSourceInventory(
                track="c00",
                source_id="repository:piscine.c00",
                source_kind="existing_repository_content",
                root_path=str(c00_root),
                discovered_candidates=len(REPOSITORY_C00_EXERCISES),
                importable_candidates=len(REPOSITORY_C00_EXERCISES),
                notes=["existing canonical bundles reused as first-pass sources"],
            )
        )
        grademe_root = self.workspace_root / "grademe 42 exam/n/success"
        discovered_candidates = (
            len([item for item in grademe_root.iterdir() if item.is_dir()])
            if grademe_root.exists()
            else 0
        )
        inventories.append(
            PiscineSourceInventory(
                track="c00",
                source_id="legacy:grademe-success-c00",
                source_kind="legacy_repository_content",
                root_path=str(grademe_root),
                discovered_candidates=discovered_candidates,
                importable_candidates=len(LEGACY_C00_IMPORTS),
                notes=[
                    "first pass promotes only deterministic c00 candidates with runnable C grading paths"
                ],
            )
        )

        grademe_c01_root = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_01/4"
        )
        discovered_c01 = (
            len([item for item in grademe_c01_root.iterdir() if item.is_dir()])
            if grademe_c01_root.exists()
            else 0
        )
        inventories.append(
            PiscineSourceInventory(
                track="c01",
                source_id="legacy:grademe-exam01-4-c01",
                source_kind="legacy_repository_content",
                root_path=str(grademe_c01_root),
                discovered_candidates=discovered_c01,
                importable_candidates=len(LEGACY_C01_IMPORTS),
                notes=list(LEGACY_C01_IMPORTS.keys()),
            )
        )

        grademe_c02_root = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_01/5"
        )
        discovered_c02 = (
            len([item for item in grademe_c02_root.iterdir() if item.is_dir()])
            if grademe_c02_root.exists()
            else 0
        )
        inventories.append(
            PiscineSourceInventory(
                track="c02",
                source_id="legacy:grademe-exam01-5-c02",
                source_kind="legacy_repository_content",
                root_path=str(grademe_c02_root),
                discovered_candidates=discovered_c02,
                importable_candidates=len(LEGACY_C02_IMPORTS),
                notes=list(LEGACY_C02_IMPORTS.keys()),
            )
        )

        grademe_c03_root_6 = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_01/6"
        )
        grademe_c03_root_7 = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_01/7"
        )
        discovered_c03 = (
            len([item for item in grademe_c03_root_6.iterdir() if item.is_dir()])
            if grademe_c03_root_6.exists()
            else 0
        ) + (
            len([item for item in grademe_c03_root_7.iterdir() if item.is_dir()])
            if grademe_c03_root_7.exists()
            else 0
        )
        inventories.append(
            PiscineSourceInventory(
                track="c03",
                source_id="legacy:grademe-exam01-67-c03",
                source_kind="legacy_repository_content",
                root_path=str(grademe_c03_root_6.parent),
                discovered_candidates=discovered_c03,
                importable_candidates=len(LEGACY_C03_IMPORTS),
                notes=list(LEGACY_C03_IMPORTS.keys()),
            )
        )

        # C04, C05, C06 inventories spanning exam_01, exam_02, exam_03, exam_04
        # Since they are scattered, we'll assign their root paths to the exam directories roughly corresponding
        # to where the exercises are primarily sourced.
        grademe_exam01_root = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_01"
        )
        grademe_exam02_root = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_02"
        )
        grademe_exam03_root = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_03"
        )
        grademe_exam04_root = (
            self.workspace_root / "grademe-main/.subjects/PISCINE_PART/exam_04"
        )

        inventories.append(
            PiscineSourceInventory(
                track="c04",
                source_id="legacy:grademe-exam020304-c04",
                source_kind="legacy_repository_content",
                root_path=str(grademe_exam04_root),
                discovered_candidates=len(LEGACY_C04_IMPORTS),
                importable_candidates=len(LEGACY_C04_IMPORTS),
                notes=list(LEGACY_C04_IMPORTS.keys()),
            )
        )

        inventories.append(
            PiscineSourceInventory(
                track="c05",
                source_id="legacy:grademe-exam03-c05",
                source_kind="legacy_repository_content",
                root_path=str(grademe_exam03_root),
                discovered_candidates=len(LEGACY_C05_IMPORTS),
                importable_candidates=len(LEGACY_C05_IMPORTS),
                notes=list(LEGACY_C05_IMPORTS.keys()),
            )
        )

        inventories.append(
            PiscineSourceInventory(
                track="c06",
                source_id="legacy:grademe-exam0103-c06",
                source_kind="legacy_repository_content",
                root_path=str(grademe_exam01_root),
                discovered_candidates=len(LEGACY_C06_IMPORTS),
                importable_candidates=len(LEGACY_C06_IMPORTS),
                notes=list(LEGACY_C06_IMPORTS.keys()),
            )
        )
        return inventories

    def build_first_pass(self, *, write: bool = True) -> PiscineDatasetImportReport:
        sources = self.discover_sources()
        imported_exercises = self._imported_exercise_records()
        imported_pools = self._imported_pool_records()
        missing_or_incomplete = self._missing_or_incomplete_entries()
        unresolved_gaps = self._unresolved_migration_gaps()
        validation = PiscineValidationSummary(
            catalog_valid=False,
            pool_valid=False,
            candidate_resolution_valid=False,
            session_progression_valid=False,
            notes=["validation did not run"],
        )

        if write:
            self._reset_directory(self.staging_root)
            self._write_accepted_content()
            self._prepare_repository_view()
            validation = self._validate_repository_view()
            report = PiscineDatasetImportReport(
                generated_at=self.generated_at,
                staging_root=str(self.staging_root),
                repository_root=str(self.repository_root),
                sources=sources,
                imported_exercises=imported_exercises,
                imported_pools=imported_pools,
                missing_or_incomplete=missing_or_incomplete,
                unresolved_migration_gaps=unresolved_gaps,
                validation=validation,
            )
            self._write_reports(report)
            self._write_status(report)
            return report

        return PiscineDatasetImportReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            repository_root=str(self.repository_root),
            sources=sources,
            imported_exercises=imported_exercises,
            imported_pools=imported_pools,
            missing_or_incomplete=missing_or_incomplete,
            unresolved_migration_gaps=unresolved_gaps,
            validation=validation,
        )

    def _imported_exercise_records(self) -> list[PiscineImportedExercise]:
        records: list[PiscineImportedExercise] = []
        for slug in REPOSITORY_C00_EXERCISES:
            records.append(
                PiscineImportedExercise(
                    exercise_id=f"piscine.c00.{slug}",
                    track="c00",
                    source_id="repository:piscine.c00",
                    source_kind="existing_repository_content",
                    origin_path=str(self.canonical_exercises_root / "c00" / slug),
                    runtime_ready=True,
                    canonical_path=f"datasets/exercises/piscine/c00/{slug}",
                )
            )
        for track in ["c00", "c01", "c02", "c03", "c04", "c05", "c06"]:
            imports_dict = globals()[f"LEGACY_{track.upper()}_IMPORTS"]
            source_id = (
                "legacy:grademe-success-c00"
                if track == "c00"
                else f"legacy:grademe-exam01-{track}"
            )
            for slug, config in imports_dict.items():
                records.append(
                    PiscineImportedExercise(
                        exercise_id=f"piscine.{track}.{slug}",
                        track=track,
                        source_id=source_id,
                        source_kind="legacy_repository_content",
                        origin_path=str(self.workspace_root / config["source_path"]),
                        runtime_ready=True,
                        canonical_path=f"datasets/exercises/piscine/{track}/{slug}",
                    )
                )
        return records

    def _imported_pool_records(self) -> list[PiscinePoolRecord]:
        return [
            PiscinePoolRecord(
                pool_id="piscine.c00.foundations",
                track="c00",
                canonical_path="datasets/pools/piscine/c00-foundations/pool.yml",
                exercise_count=4,
                runtime_ready=True,
            ),
            PiscinePoolRecord(
                pool_id="piscine.c01.core",
                track="c01",
                canonical_path="datasets/pools/piscine/c01-core/pool.yml",
                exercise_count=len(LEGACY_C01_IMPORTS),
                runtime_ready=True,
            ),
            PiscinePoolRecord(
                pool_id="piscine.c02.core",
                track="c02",
                canonical_path="datasets/pools/piscine/c02-core/pool.yml",
                exercise_count=len(LEGACY_C02_IMPORTS),
                runtime_ready=True,
            ),
            PiscinePoolRecord(
                pool_id="piscine.c03.core",
                track="c03",
                canonical_path="datasets/pools/piscine/c03-core/pool.yml",
                exercise_count=len(LEGACY_C03_IMPORTS),
                runtime_ready=True,
            ),
            PiscinePoolRecord(
                pool_id="piscine.c04.core",
                track="c04",
                canonical_path="datasets/pools/piscine/c04-core/pool.yml",
                exercise_count=len(LEGACY_C04_IMPORTS),
                runtime_ready=True,
            ),
            PiscinePoolRecord(
                pool_id="piscine.c05.core",
                track="c05",
                canonical_path="datasets/pools/piscine/c05-core/pool.yml",
                exercise_count=len(LEGACY_C05_IMPORTS),
                runtime_ready=True,
            ),
            PiscinePoolRecord(
                pool_id="piscine.c06.core",
                track="c06",
                canonical_path="datasets/pools/piscine/c06-core/pool.yml",
                exercise_count=len(LEGACY_C06_IMPORTS),
                runtime_ready=True,
            ),
        ]

    def _missing_or_incomplete_entries(self) -> list[dict[str, object]]:
        return [
            {
                "track": "shell00",
                "kind": "exercise_set",
                "identifier": "shell00",
                "state": "missing_runtime_content",
                "reason": "no deterministic legacy runtime bundles were found in the current workspace",
            },
            {
                "track": "shell01",
                "kind": "exercise_set",
                "identifier": "shell01",
                "state": "missing_runtime_content",
                "reason": "no deterministic legacy runtime bundles were found in the current workspace",
            },
            {
                "track": "shell00",
                "kind": "pool",
                "identifier": "piscine.shell00.foundations",
                "state": "blocked",
                "reason": "pool generation is blocked until at least one runtime-valid shell00 exercise bundle exists",
            },
            {
                "track": "shell01",
                "kind": "pool",
                "identifier": "piscine.shell01.foundations",
                "state": "blocked",
                "reason": "pool generation is blocked until at least one runtime-valid shell01 exercise bundle exists",
            },
        ]

    def _unresolved_migration_gaps(self) -> list[str]:
        return [
            "shell00 and shell01 have no deterministic runtime bundle sources in the current workspace",
            "the current canonical grading contract is C-only, so shell exercises cannot be promoted as runtime-ready without a shell runtime contract",
            "Subjects PDFs are available only for C00 to C13; no shell00 or shell01 PDF metadata is present locally",
        ]

    def _write_accepted_content(self) -> None:
        accepted_exercises_root = self.accepted_root / "datasets/exercises/piscine/c00"
        for slug in REPOSITORY_C00_EXERCISES:
            source = self.canonical_exercises_root / "c00" / slug
            destination = accepted_exercises_root / slug
            shutil.copytree(source, destination, dirs_exist_ok=True)

        for track in ["c00", "c01", "c02", "c03", "c04", "c05", "c06"]:
            imports_dict = globals()[f"LEGACY_{track.upper()}_IMPORTS"]
            track_exercises_root = (
                self.accepted_root / f"datasets/exercises/piscine/{track}"
            )
            for slug, config in imports_dict.items():
                bundle_root = track_exercises_root / slug
                canonical_bundle = self.canonical_exercises_root / track / slug
                if canonical_bundle.exists():
                    shutil.copytree(canonical_bundle, bundle_root, dirs_exist_ok=True)
                    continue
                bundle_root.mkdir(parents=True, exist_ok=True)
                source_path = self.workspace_root / config["source_path"]
                reference_source = source_path.read_text(encoding="utf-8")
                starter_dir = bundle_root / "starter"
                reference_dir = bundle_root / "reference"
                tests_dir = bundle_root / "tests"
                starter_dir.mkdir(parents=True, exist_ok=True)
                reference_dir.mkdir(parents=True, exist_ok=True)
                tests_dir.mkdir(parents=True, exist_ok=True)

                file_name = f"{slug}.c"
                (bundle_root / "statement.md").write_text(
                    config["statement"], encoding="utf-8"
                )
                (starter_dir / file_name).write_text(
                    str(config["starter"]), encoding="utf-8"
                )
                (reference_dir / file_name).write_text(
                    reference_source, encoding="utf-8"
                )
                (tests_dir / "tests.yml").write_text(
                    yaml.safe_dump(config["tests"], sort_keys=False),
                    encoding="utf-8",
                )
                if config.get("harness") is not None:
                    (tests_dir / "main.c").write_text(
                        str(config["harness"]), encoding="utf-8"
                    )

                manifest = self._legacy_manifest(track, slug, config)
                (bundle_root / "exercise.yml").write_text(
                    yaml.safe_dump(manifest, sort_keys=False),
                    encoding="utf-8",
                )

        pools = {
            "c00-foundations": self._c00_pool_manifest(),
            "c01-core": self._c01_pool_manifest(),
            "c02-core": self._c02_pool_manifest(),
            "c03-core": self._c03_pool_manifest(),
            "c04-core": self._c04_pool_manifest(),
            "c05-core": self._c05_pool_manifest(),
            "c06-core": self._c06_pool_manifest(),
        }
        for pool_id, pool_manifest in pools.items():
            pool_root = self.accepted_root / f"datasets/pools/piscine/{pool_id}"
            canonical_pool_root = self.canonical_pools_root / pool_id
            if canonical_pool_root.exists():
                shutil.copytree(canonical_pool_root, pool_root, dirs_exist_ok=True)
                continue
            pool_root.mkdir(parents=True, exist_ok=True)
            (pool_root / "pool.yml").write_text(
                yaml.safe_dump(pool_manifest, sort_keys=False),
                encoding="utf-8",
            )

    def _legacy_manifest(
        self, group: str, slug: str, config: dict[str, object]
    ) -> dict[str, object]:
        compile_mode = str(config["compile_mode"])
        manifest = {
            "schema_version": 1,
            "id": f"piscine.{group}.{slug}",
            "slug": slug,
            "title": config["title"],
            "summary": config["summary"],
            "track": "piscine",
            "group": group,
            "source": {
                "kind": "legacy_import",
                "origin_id": f"{group}.{slug}",
                "origin_path": str(config["source_path"]),
                "copyright_status": "unknown",
            },
            "language": "c",
            "difficulty": {
                "level": int(config["difficulty"]),
                "category": "beginner",
            },
            "pedagogy": {
                "modes": ["practice", "observation"],
                "concepts": list(config["concepts"]),
                "skills": list(config["skills"]),
                "misconceptions": list(config["misconceptions"]),
                "prerequisite_ids": [],
                "followup_ids": [],
                "estimated_minutes": int(config["estimated_minutes"]),
            },
            "files": {
                "statement": "statement.md",
                "starter_dir": "starter",
                "reference_dir": "reference",
                "tests_dir": "tests",
            },
            "student_contract": {
                "expected_files": [f"{slug}.c"],
                "allowed_functions": config.get("allowed_functions", ["write"]),
                "forbidden_functions": [],
                "required_headers": config.get("required_headers", ["unistd.h"]),
                "output_contract": {
                    "channel": "stdout",
                    "newline_policy": "exact",
                },
                "norm": {
                    "enabled": True,
                    "profile": "42_norm_v1",
                },
            },
            "build": {
                "compiler": "gcc",
                "standard": "c11",
                "flags": ["-Wall", "-Wextra", "-Werror"],
                "link_flags": [],
                "compile_mode": compile_mode,
                "entry_files": [f"{slug}.c"],
            },
            "runtime": {
                "argv_policy": "allowed",
                "stdin_policy": "none",
                "timeout_seconds": 2,
                "memory_limit_mb": 64,
                "file_write_policy": "deny",
                "network_access": False,
            },
            "grading": {
                "strategy": "output_diff",
                "comparator": "builtin.comparator.output_diff",
                "rubric_id": "rubric.c.default",
                "pass_policy": {
                    "mode": "all_tests",
                    "threshold": 1.0,
                },
                "edge_case_suite_id": f"piscine.{group}.{slug}",
                "analyzer_ids": ["builtin.analyzer.failure_classifier"],
            },
            "variants": {
                "default": "normal",
                "available": [
                    {
                        "id": "normal",
                        "kind": "normal",
                        "starter_dir": "starter",
                        "reference_dir": "reference",
                        "tests_dir": "tests",
                        "description": "Standard implementation path.",
                    }
                ],
            },
            "learning": config["learning"],
            "metadata": {
                "author": "platform.import_legacy",
                "reviewers": [],
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }
        return manifest

    def _c00_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c00.foundations",
            "title": "C00 Foundations",
            "track": "piscine",
            "mode": "practice",
            "description": "Ordered early piscine pool for single-character, digit, countdown, and string output exercises.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 3600,
                "per_level_time_seconds": 900,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "Single Character Output",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 600,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c00.ft_putchar",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "Digit Sequence Output",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 600,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c00.ft_print_numbers",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
                {
                    "level": 2,
                    "title": "Countdown Output",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 600,
                    "unlock_if": {"all_of": [1], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c00.ft_countdown",
                            "variant": "normal",
                            "order": 30,
                        }
                    ],
                },
                {
                    "level": 3,
                    "title": "String Output",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [2], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c00.ft_putstr",
                            "variant": "normal",
                            "order": 40,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _c01_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c01.core",
            "title": "C01 Core",
            "track": "piscine",
            "mode": "practice",
            "description": "Pool for basic string manipulation and function with harness testing.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 3600,
                "per_level_time_seconds": 900,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "String Length",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c01.ft_strlen",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "String Copy",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c01.ft_strcpy",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _c02_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c02.core",
            "title": "C02 Core",
            "track": "piscine",
            "mode": "practice",
            "description": "Pool for string transformations and character manipulation.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 3600,
                "per_level_time_seconds": 900,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "Case Flipping",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c02.ulstr",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "Search and Replace",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c02.search_and_replace",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
                {
                    "level": 2,
                    "title": "Repeated Characters",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [1], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c02.repeat_alpha",
                            "variant": "normal",
                            "order": 30,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _c03_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c03.core",
            "title": "C03 Core",
            "track": "piscine",
            "mode": "practice",
            "description": "Pool for advanced string scanning and manipulation.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 4500,
                "per_level_time_seconds": 900,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "First Word",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c03.first_word",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "Reverse Print",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c03.rev_print",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
                {
                    "level": 2,
                    "title": "RotOne",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [1], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c03.rotone",
                            "variant": "normal",
                            "order": 30,
                        }
                    ],
                },
                {
                    "level": 3,
                    "title": "Rot13",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [2], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c03.rot_13",
                            "variant": "normal",
                            "order": 40,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _c04_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c04.core",
            "title": "C04 Core",
            "track": "piscine",
            "mode": "practice",
            "description": "Pool for numeric conversions and base representations.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 4500,
                "per_level_time_seconds": 900,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "ASCII to Integer",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c04.ft_atoi",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "Integer to ASCII",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c04.ft_itoa",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
                {
                    "level": 2,
                    "title": "ASCII to Integer Base",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 1200,
                    "unlock_if": {"all_of": [1], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c04.ft_atoi_base",
                            "variant": "normal",
                            "order": 30,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _c05_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c05.core",
            "title": "C05 Core",
            "track": "piscine",
            "mode": "practice",
            "description": "Pool for mathematical algorithms and prime numbers.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 6000,
                "per_level_time_seconds": 1200,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "Power of 2",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c05.is_power_of_2",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "Greatest Common Divisor",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c05.pgcd",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
                {
                    "level": 2,
                    "title": "Least Common Multiple",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [1], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c05.lcm",
                            "variant": "normal",
                            "order": 30,
                        }
                    ],
                },
                {
                    "level": 3,
                    "title": "Add Prime Sum",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 1200,
                    "unlock_if": {"all_of": [2], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c05.add_prime_sum",
                            "variant": "normal",
                            "order": 40,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _c06_pool_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "id": "piscine.c06.core",
            "title": "C06 Core",
            "track": "piscine",
            "mode": "practice",
            "description": "Pool for command-line arguments and standard output.",
            "selection": {
                "strategy": "ordered",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": 3600,
                "per_level_time_seconds": 900,
                "cooldown": {
                    "enabled": True,
                    "seconds": 30,
                    "scope": "level",
                },
            },
            "levels": [
                {
                    "level": 0,
                    "title": "First Parameter",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c06.aff_first_param",
                            "variant": "normal",
                            "order": 10,
                        }
                    ],
                },
                {
                    "level": 1,
                    "title": "Last Parameter",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 900,
                    "unlock_if": {"all_of": [0], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c06.aff_last_param",
                            "variant": "normal",
                            "order": 20,
                        }
                    ],
                },
                {
                    "level": 2,
                    "title": "Parameter Sum",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": 1200,
                    "unlock_if": {"all_of": [1], "any_of": []},
                    "exercise_refs": [
                        {
                            "exercise_id": "piscine.c06.paramsum",
                            "variant": "normal",
                            "order": 30,
                        }
                    ],
                },
            ],
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "draft",
            },
        }

    def _prepare_repository_view(self) -> None:
        repo_root = self.repository_root
        repo_root.mkdir(parents=True, exist_ok=True)

        copy_pairs = (
            (
                self.accepted_root / "datasets/exercises",
                repo_root / "datasets/exercises",
            ),
            (self.accepted_root / "datasets/pools", repo_root / "datasets/pools"),
            (
                self.platform_root / "core/grading/builtins",
                repo_root / "core/grading/builtins",
            ),
            (
                self.platform_root / "core/sandbox/profiles",
                repo_root / "core/sandbox/profiles",
            ),
        )
        for source, destination in copy_pairs:
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)

        for relative in (
            "storage/sessions",
            "storage/attempts",
            "runtime/reports",
            "runtime/workspaces",
            "runtime/traces",
            "runtime/cache",
            "runtime/manual_submissions",
        ):
            (repo_root / relative).mkdir(parents=True, exist_ok=True)

    def _validate_repository_view(self) -> PiscineValidationSummary:
        notes: list[str] = []
        catalog_valid = False
        pool_valid = False
        candidate_resolution_valid = False
        session_progression_valid = False
        session_progression_order: list[str] = []
        graded_exercises: list[dict[str, object]] = []

        try:
            catalog = CatalogService(self.repository_root)
            exercise_index = catalog.build_index(refresh=True)
            pool_index = catalog.build_pool_index(refresh=True)
            catalog_valid = True
            expected_pools = [
                "piscine.c00.foundations",
                "piscine.c01.core",
                "piscine.c02.core",
                "piscine.c03.core",
                "piscine.c04.core",
                "piscine.c05.core",
                "piscine.c06.core",
            ]
            pool_valid = all(p in pool_index for p in expected_pools)
            notes.append(
                f"validated exercises={len(exercise_index)} pools={len(pool_index)}"
            )
        except CatalogValidationError as exc:
            notes.extend(failure.render() for failure in exc.failures)
            return PiscineValidationSummary(
                catalog_valid=False,
                pool_valid=False,
                candidate_resolution_valid=False,
                session_progression_valid=False,
                notes=notes,
            )

        try:
            pool_engine = PoolEngineService(self.repository_root)
            first_candidates = pool_engine.resolve_candidate_exercises(
                "piscine.c00.foundations",
                session_history=[],
                session_id="session.piscine.import.validation",
            )
            second_candidates = pool_engine.resolve_candidate_exercises(
                "piscine.c00.foundations",
                session_history=[
                    SessionExerciseRecord(
                        attempt_id="attempt.001",
                        exercise_id="piscine.c00.ft_putchar",
                        variant_id="normal",
                        pool_id="piscine.c00.foundations",
                        created_at=self.generated_at,
                        passed=True,
                    )
                ],
                session_id="session.piscine.import.validation",
            )
            candidate_resolution_valid = (
                len(first_candidates) == 1
                and first_candidates[0].exercise_id == "piscine.c00.ft_putchar"
                and len(second_candidates) == 1
                and second_candidates[0].exercise_id == "piscine.c00.ft_print_numbers"
            )
        except Exception as exc:  # pragma: no cover - defensive
            notes.append(f"candidate resolution failed: {exc}")

        try:
            grading_engine = GradingEngine(self.repository_root)
            for exercise_id in (
                "piscine.c00.ft_putchar",
                "piscine.c00.ft_print_numbers",
                "piscine.c00.ft_countdown",
                "piscine.c00.ft_putstr",
                "piscine.c01.ft_strlen",
                "piscine.c01.ft_strcpy",
                "piscine.c02.ulstr",
                "piscine.c02.search_and_replace",
                "piscine.c02.repeat_alpha",
                "piscine.c03.first_word",
                "piscine.c03.rev_print",
                "piscine.c03.rotone",
                "piscine.c03.rot_13",
                "piscine.c04.ft_atoi",
                "piscine.c04.ft_itoa",
                "piscine.c04.ft_atoi_base",
                "piscine.c05.is_power_of_2",
                "piscine.c05.pgcd",
                "piscine.c05.lcm",
                "piscine.c05.add_prime_sum",
                "piscine.c06.aff_first_param",
                "piscine.c06.aff_last_param",
                "piscine.c06.paramsum",
            ):
                exercise = catalog.load_exercise(exercise_id)
                pool_id = (
                    "piscine.c00.foundations"
                    if "c00" in exercise_id
                    else f"piscine.{exercise_id.split('.')[1]}.core"
                )
                report = grading_engine.grade_submission(
                    AttemptContext(
                        attempt_id=f"probe.{exercise_id.replace('.', '-')}",
                        session_id="probe.session",
                        user_id="probe.user",
                        exercise_id=exercise_id,
                        variant_id="normal",
                        mode="piscine",
                        pool_id=pool_id,
                        submission_root=exercise.reference_dir,
                        attempt_index_for_exercise=1,
                    )
                )
                graded_exercises.append(
                    {
                        "exercise_id": exercise_id,
                        "passed": bool(report["evaluation"]["passed"]),
                        "failure_class": report["evaluation"]["failure_class"],
                        "report_id": report["report_id"],
                    }
                )
        except Exception as exc:  # pragma: no cover - defensive
            notes.append(f"grading validation failed: {exc}")

        try:
            session_service = PiscineSessionService(self.repository_root)
            pools_to_order = {
                "piscine.c00.foundations": [
                    "piscine.c00.ft_putchar",
                    "piscine.c00.ft_print_numbers",
                    "piscine.c00.ft_countdown",
                    "piscine.c00.ft_putstr",
                ],
                "piscine.c01.core": [
                    "piscine.c01.ft_strlen",
                    "piscine.c01.ft_strcpy",
                ],
                "piscine.c02.core": [
                    "piscine.c02.ulstr",
                    "piscine.c02.search_and_replace",
                    "piscine.c02.repeat_alpha",
                ],
                "piscine.c03.core": [
                    "piscine.c03.first_word",
                    "piscine.c03.rev_print",
                    "piscine.c03.rotone",
                    "piscine.c03.rot_13",
                ],
                "piscine.c04.core": [
                    "piscine.c04.ft_atoi",
                    "piscine.c04.ft_itoa",
                    "piscine.c04.ft_atoi_base",
                ],
                "piscine.c05.core": [
                    "piscine.c05.is_power_of_2",
                    "piscine.c05.pgcd",
                    "piscine.c05.lcm",
                    "piscine.c05.add_prime_sum",
                ],
                "piscine.c06.core": [
                    "piscine.c06.aff_first_param",
                    "piscine.c06.aff_last_param",
                    "piscine.c06.paramsum",
                ],
            }
            session_progression_valid = True
            for pool_id, expected_order in pools_to_order.items():
                session = session_service.start_session(
                    pool_id, user_id="validation.runner"
                )
                order = []
                while session["state"] == "active":
                    current_id = session["current_assignment"]["exercise_id"]
                    order.append(current_id)
                    exercise = catalog.load_exercise(current_id)
                    submission = session_service.submit_submission(
                        session["session_id"], exercise.reference_dir
                    )
                    session = submission["session"]
                session_progression_order.extend(order)
                if session["state"] != "completed" or order != expected_order:
                    session_progression_valid = False
        except Exception as exc:  # pragma: no cover - defensive
            notes.append(f"session progression validation failed: {exc}")

        return PiscineValidationSummary(
            catalog_valid=catalog_valid,
            pool_valid=pool_valid,
            candidate_resolution_valid=candidate_resolution_valid,
            session_progression_valid=session_progression_valid
            and all(item.get("passed") for item in graded_exercises),
            session_progression_order=session_progression_order,
            graded_exercises=graded_exercises,
            notes=notes,
        )

    def _write_reports(self, report: PiscineDatasetImportReport) -> None:
        self.reports_root.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        self._write_yaml(self.report_path, payload)
        self._write_yaml(
            self.reports_root / "piscine_sources.latest.yml",
            {"sources": payload["sources"]},
        )
        self._write_yaml(
            self.reports_root / "piscine_validation.latest.yml",
            {"validation": payload["validation"]},
        )
        self._write_yaml(
            self.reports_root / "piscine_missing.latest.yml",
            {
                "missing_or_incomplete": payload["missing_or_incomplete"],
                "unresolved_migration_gaps": payload["unresolved_migration_gaps"],
            },
        )

    def _write_status(self, report: PiscineDatasetImportReport) -> None:
        payload = report.to_dict()
        summary = payload["summary"]
        lines = [
            "# PISCINE_DATASET_STATUS",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Staging root: `{report.staging_root}`",
            f"- Repository root: `{report.repository_root}`",
            "",
            "## Discovered Source Counts",
            "",
        ]
        for track in FIRST_PASS_TRACKS:
            matching = [item for item in report.sources if item.track == track]
            lines.append(
                f"- `{track}`: sources=`{len(matching)}`, "
                f"discovered candidates=`{sum(item.discovered_candidates for item in matching)}`, "
                f"importable candidates=`{sum(item.importable_candidates for item in matching)}`"
            )
        lines.extend(["", "## Imported Canonical Exercise Counts", ""])
        imported_counts = Counter(item.track for item in report.imported_exercises)
        for track in FIRST_PASS_TRACKS:
            lines.append(f"- `{track}`: `{imported_counts.get(track, 0)}`")
        lines.extend(["", "## Imported Pool Counts", ""])
        pool_counts = Counter(item.track for item in report.imported_pools)
        for track in FIRST_PASS_TRACKS:
            lines.append(f"- `{track}`: `{pool_counts.get(track, 0)}`")
        lines.extend(["", "## Missing Or Incomplete Exercises", ""])
        for item in report.missing_or_incomplete:
            lines.append(
                f"- `{item['identifier']}` ({item['track']}, {item['kind']}): `{item['state']}` - {item['reason']}"
            )
        lines.extend(["", "## Unresolved Migration Gaps", ""])
        for gap in report.unresolved_migration_gaps:
            lines.append(f"- {gap}")
        lines.extend(["", "## Validation", ""])
        lines.extend(
            [
                f"- Catalog validation: `{summary['catalog_valid']}`",
                f"- Pool validation: `{summary['pool_valid']}`",
                f"- Pool candidate resolution: `{summary['candidate_resolution_valid']}`",
                f"- Piscine session progression: `{summary['session_progression_valid']}`",
            ]
        )
        if report.validation.session_progression_order:
            lines.append(
                f"- Session progression order: `{', '.join(report.validation.session_progression_order)}`"
            )
        lines.extend(["", "## Grading Validation", ""])
        for item in report.validation.graded_exercises:
            lines.append(
                f"- `{item['exercise_id']}`: passed=`{item['passed']}`, failure_class=`{item['failure_class']}`"
            )
        if report.validation.notes:
            lines.extend(["", "## Notes", ""])
            for note in report.validation.notes:
                lines.append(f"- {note}")
        self.status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _reset_directory(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    def _write_yaml(self, path: Path, payload: object) -> None:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

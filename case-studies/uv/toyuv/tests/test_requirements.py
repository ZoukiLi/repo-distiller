import unittest

from toyuv.errors import RequirementError
from toyuv.requirements import Requirement, Version, normalize_name


class RequirementTests(unittest.TestCase):
    def test_versions_are_numeric_and_ordered(self) -> None:
        self.assertLess(Version.parse("1.9"), Version.parse("1.10"))
        self.assertEqual(str(Version.parse("2")), "2.0.0")

    def test_requirement_combines_all_constraints(self) -> None:
        requirement = Requirement.parse("My_Package>=1.2,<2")
        self.assertEqual(requirement.name, "my-package")
        self.assertTrue(requirement.allows(Version.parse("1.5")))
        self.assertFalse(requirement.allows(Version.parse("2.0")))

    def test_normalization_collapses_python_name_separators(self) -> None:
        self.assertEqual(normalize_name("Some.package_Name"), "some-package-name")

    def test_unsupported_pep_508_syntax_is_rejected(self) -> None:
        with self.assertRaises(RequirementError):
            Requirement.parse("demo[extra]>=1")


if __name__ == "__main__":
    unittest.main()

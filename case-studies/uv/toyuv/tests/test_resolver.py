import unittest

from toyuv.errors import ResolutionError
from toyuv.registry import Registry
from toyuv.requirements import Requirement, Version
from toyuv.resolver import Resolver


class ResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = Registry.builtin()

    def test_selects_latest_compatible_transitive_versions(self) -> None:
        resolution = Resolver(self.registry).resolve([Requirement.parse("greet-demo")])
        self.assertEqual(resolution.packages["greet-demo"].version, Version.parse("2"))
        self.assertEqual(resolution.packages["color-demo"].version, Version.parse("2"))

    def test_existing_lock_is_a_preference_not_a_hard_constraint(self) -> None:
        resolver = Resolver(self.registry, {"greet-demo": Version.parse("1")})
        resolution = resolver.resolve([Requirement.parse("greet-demo")])
        self.assertEqual(resolution.packages["greet-demo"].version, Version.parse("1"))
        self.assertEqual(resolution.packages["color-demo"].version, Version.parse("1"))

    def test_conflict_reports_direct_and_transitive_origins(self) -> None:
        with self.assertRaises(ResolutionError) as caught:
            Resolver(self.registry).resolve(
                [Requirement.parse("greet-demo>=2"), Requirement.parse("legacy-demo")]
            )
        message = str(caught.exception)
        self.assertIn("greet-demo", message)
        self.assertIn("legacy-demo==1.0.0", message)
        self.assertIn("project", message)


if __name__ == "__main__":
    unittest.main()

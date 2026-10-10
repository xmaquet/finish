import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera.devices import assign_camera_labels


class CameraLabelTest(unittest.TestCase):
    def test_directshow_names_follow_the_opened_indexes(self) -> None:
        choices = assign_camera_labels([0, 1], ["Integrated Camera", "Web Camera"])
        self.assertEqual(choices[0].label, "Caméra 0 — Integrated Camera")
        self.assertEqual(choices[1].label, "Caméra 1 — Web Camera")

    def test_infrared_list_is_not_shifted_onto_the_webcam(self) -> None:
        choices = assign_camera_labels(
            [0, 1],
            ["Integrated IR Camera", "Integrated Camera", "Web Camera"],
        )
        self.assertEqual([choice.label for choice in choices], ["Caméra 0", "Caméra 1"])


if __name__ == "__main__":
    unittest.main()

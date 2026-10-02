"""Embodiment heuristic: the cases that motivated it, and the false positives found while building it."""
import unittest

from conformance.embodiment import classify


def info(robot_type=None, **features):
    return {"robot_type": robot_type, "features": {k: {"dtype": "float32", "names": v} for k, v in features.items()}}


class Embodiment(unittest.TestCase):
    def test_driving_dataset_is_outside(self):  # shape of yaak-ai/lerobot-driving-school
        r = classify(info("KIA Niro EV 2023", **{"action.continuous": {"axes": ["gas_pedal_normalized", "brake_pedal_normalized", "steering_angle_normalized"]},
                                                 "observation.state.vehicle": {"axes": ["speed", "heading", "hp_loc_latitude", "hp_loc_longitude"]}}))
        self.assertEqual((r["category"], r["fit"]), ("vehicle", "outside"))

    def test_racecar_robot_type(self):
        self.assertEqual(classify(info("racecar"))["category"], "vehicle")

    def test_screwdriver_is_not_a_vehicle(self):
        self.assertEqual(classify(info("koch_screwdriver_follower"))["category"], "arm")

    def test_smpl_is_human_motion(self):
        self.assertEqual(classify(info(None, **{"observation.smpl_pose": ["a"]}))["fit"], "outside")

    def test_human_in_name_is_not_evidence(self):
        self.assertEqual(classify(info("robocasa_x"), "lerobot/robocasa_target_human_unified")["fit"], "fits")
        self.assertEqual(classify(info("unknown"), "u/human_demos")["fit"], "unclear")

    def test_common_robots(self):
        cases = {"so101_follower": "arm", "aloha": "bimanual", "bi_so100_follower": "bimanual", "unitree_g1": "humanoid",
                 "hello_stretch": "mobile_manipulator", "franka": "arm", "yam": "arm", "bi_yam_follower": "bimanual"}
        for rt, cat in cases.items():
            with self.subTest(rt):
                self.assertEqual(classify(info(rt))["category"], cat)

    def test_names_fallback_and_name_fallback(self):
        self.assertEqual(classify(info("unknown", **{"observation.state": ["shoulder_pan.pos", "gripper.pos"]}))["category"], "arm")
        self.assertEqual(classify(info("unknown"), "lerobot/xarm_lift_medium")["category"], "arm")
        self.assertEqual(classify(info("unknown"), "lerobot/pusht")["category"], "unclear")


if __name__ == "__main__":
    unittest.main()

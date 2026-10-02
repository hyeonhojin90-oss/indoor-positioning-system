import unittest
from augment_portal_positions import moved_label

class PositionLabelTests(unittest.TestCase):
    def test_mirror_and_clipping_do_not_label_invisible_portal(self):
        self.assertAlmostEqual(moved_label([0,.2,.5,.1,.6],flip=True)[1],.8)
        self.assertAlmostEqual(moved_label([0,.5,.5,.2,.6],shift=.15)[1],.65)
        self.assertIsNone(moved_label([0,.95,.5,.2,.6],shift=.15))
        visible=moved_label([0,.9,.5,.2,.6],shift=.05)
        self.assertAlmostEqual(visible[3],.15);self.assertLessEqual(visible[1]+visible[3]/2,1)
if __name__=='__main__':unittest.main()

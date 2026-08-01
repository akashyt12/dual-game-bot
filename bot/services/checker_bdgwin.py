import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from bdgwin_checker import BDGWinAccountChecker, predict_bs, predict_color, result_to_bs, result_to_color

__all__ = ["BDGWinAccountChecker", "predict_bs", "predict_color", "result_to_bs", "result_to_color"]

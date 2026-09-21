"""Portable settings and optional VTK rendering/interaction regression tests."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from yingguang_frc.visualization.settings import RenderSettings

ROOT=Path(__file__).resolve().parents[1]
HAS_VTK=importlib.util.find_spec("pyvista") is not None


class SettingsTests(unittest.TestCase):
    def test_round_trip_camera_and_physical_scales(self):
        s=RenderSettings(density_max=2.8e22,time_us=4.,camera_position=[[-20.,-80.,30.],[0.,0.,0.],[0.,0.,1.]])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"view.json"
            s.save(path)
            self.assertEqual(asdict(s),asdict(RenderSettings.load(path)))

    def test_invalid_values_are_rejected(self):
        for name,value in [("opacity",-1),("density_max",0),("density_max",float('nan')),
                           ("density_cutoff",1),("line_density",2.5),("fps",0),
                           ("smoothing_z_cm",-1),("quality","huge")]:
            s=RenderSettings()
            setattr(s,name,value)
            with self.assertRaises(ValueError):
                s.validate()
        with self.assertRaises(ValueError):
            RenderSettings(camera_position=[[0,0,0],[0,0,0],[0,0,1]]).validate()
        with self.assertRaises(ValueError):
            RenderSettings(camera_position=[1,2,3]).validate()

    def test_repository_preset_is_valid(self):
        s=RenderSettings.load(ROOT/'configs/render/presentation.json')
        self.assertFalse(s.auto_exposure)
        self.assertEqual(s.quality,'high')


@unittest.skipUnless(HAS_VTK,"Install the render extra for visualization tests")
class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from yingguang_frc.analysis.openpmd import load_series
        cls.frames=load_series(ROOT/"results/corrected-mirrors/sample")

    def test_temporal_interpolation_preserves_source_and_last_frame(self):
        from yingguang_frc.visualization.rendering import frame_at_time,select_frames
        a,b=self.frames[:2]
        old=a['rho'].copy()
        time=(a['t']+b['t'])/2*1e6
        fr=frame_at_time(self.frames,time)
        np.testing.assert_allclose(fr['rho'],(a['rho']+b['rho'])/2)
        np.testing.assert_array_equal(a['rho'],old)
        self.assertIs(select_frames(self.frames,2)[-1],self.frames[-1])
        with self.assertRaises(ValueError):
            frame_at_time(self.frames,99)

    def test_volume_is_visible_and_cache_does_not_modify_measurements(self):
        import pyvista as pv
        from yingguang_frc.visualization.rendering import PlasmaScene
        s=RenderSettings(show_lines=False,show_geometry=False,opacity=0)
        original=self.frames[-1]['rho'].copy()
        p=pv.Plotter(off_screen=True,window_size=(640,300))
        try:
            scene=PlasmaScene(p,self.frames[0],s,dimensions=(96,48))
            scene.draw(self.frames[-1])
            invisible=p.screenshot(return_img=True).copy()
            s.opacity=.7
            scene.draw(self.frames[-1])
            visible=p.screenshot(return_img=True).copy()
            # Central crop excludes labels/bars: this catches a missing VTK volume pass.
            delta=np.abs(visible[80:220,150:490].astype(float)-invisible[80:220,150:490])
            self.assertGreater(delta.mean(),2.)
            self.assertGreater((delta.max(axis=2)>20).sum(),500)
            self.assertEqual(scene.density_scale,3.5e22)
            np.testing.assert_array_equal(original,self.frames[-1]['rho'])
            scene.cache_limit=2
            for fr in self.frames:
                scene.draw(fr)
            self.assertLessEqual(len(scene.cache),2)
        finally:
            p.close()

    def test_viewer_tuning_scrub_playback_and_saved_camera(self):
        from yingguang_frc.visualization.interactive import Viewer
        with tempfile.TemporaryDirectory() as td:
            v=Viewer(self.frames,RenderSettings(show_lines=False),ROOT/"results/corrected-mirrors/sample",td,
                     size=(1000,700),off_screen=True)
            try:
                v.seek(self.frames[-1]['t']*1e6)
                self.assertEqual(v.k,3)
                v.sliders['opacity'].GetRepresentation().SetValue(.55)
                v.sliders['opacity'].InvokeEvent('EndInteractionEvent')
                v.buttons['show_geometry'].GetRepresentation().SetState(0)
                v.buttons['show_geometry'].InvokeEvent('StateChangedEvent')
                self.assertEqual(v.settings.opacity,.55)
                self.assertTrue(all(not a.visibility for a in v.scene.geometry))
                v.set_value('show_zero_field',True)
                self.assertGreater(v.scene.cache[next(reversed(v.scene.cache))][2].n_points,0)
                v.set_value('show_zero_field',False)
                v.set_camera('side')
                saved=RenderSettings.load(v.save_settings())
                self.assertEqual(saved.camera,'side')
                self.assertIsNotNone(saved.camera_position)
                snapshot=v.screenshot()
                self.assertGreater(snapshot.stat().st_size,1000)
                metadata=json.loads(snapshot.with_suffix('.metadata.json').read_text())
                self.assertEqual(metadata['settings']['quality'],'high')
                self.assertEqual(metadata['settings']['camera_position'],saved.camera_position)
                self.assertAlmostEqual(metadata['settings']['parallel_scale'],saved.parallel_scale)
                self.assertEqual(v.settings.quality,'interactive')
                v.toggle_play()
                v.last_tick=0
                v.tick()
                self.assertEqual(v.k,0)
                self.assertTrue(v.playing)
                v.p.window_size=(1200,800)
                v.resize_controls()
            finally:
                v.p.close()


if __name__=='__main__':
    unittest.main()

"""Interactive plasma viewer with live tuning and reproducible exports."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import time

import numpy as np
import pyvista as pv

from yingguang_frc.analysis.openpmd import load_series
from yingguang_frc.visualization.rendering import PlasmaScene, select_frames
from yingguang_frc.visualization.settings import RenderSettings, QUALITY


class Viewer:
    def __init__(self, frames, settings, run_dir, output_dir, size=(1600,900), off_screen=False):
        self.frames = frames
        self.settings = settings.validate()
        self.run_dir = Path(run_dir)
        self.output_dir = Path(output_dir)
        self.times = np.asarray([f["t"]*1e6 for f in frames])
        self.k = int(np.abs(self.times-settings.time_us).argmin())
        self.playing = False
        self.last_tick = time.monotonic()
        self.ready = False
        self.sliders = {}
        self.buttons = {}
        self.p = pv.Plotter(shape=(1,2), col_weights=[.76,.24], border=False,
                            window_size=size, off_screen=off_screen,
                            title="Yingguang-I · plasma studio")
        self.p.subplot(0,0)
        self.scene = PlasmaScene(self.p,frames[0],settings)
        self.time_slider = self.p.add_slider_widget(
            self.seek, [self.times[0], max(self.times[-1],self.times[0]+1e-6)],
            value=self.times[self.k],title="Simulation time (µs)",pointa=(.13,.14),
            pointb=(.83,.14),style="modern",color="#67dbe8",title_color="#adc0d3",
            title_height=.018,fmt="%.3f",interaction_event="end",
            slider_width=.018,tube_width=.004)
        time_rep=self.time_slider.GetRepresentation()
        time_rep.GetPoint1Coordinate().SetCoordinateSystemToNormalizedViewport()
        time_rep.GetPoint2Coordinate().SetCoordinateSystemToNormalizedViewport()
        time_rep.GetPoint1Coordinate().SetValue(.13,.14)
        time_rep.GetPoint2Coordinate().SetValue(.83,.14)
        time_rep.SetSliderLength(.015)
        self.p.add_text("SPACE play/pause   Left/Right step   1/2/3 camera   R reset   S export   W save",
                        position=(.035,.012),viewport=True,font_size=8,color="#7c93aa")
        self.p.subplot(0,1)
        self.p.set_background("#101a28", all_renderers=False)
        self.p.add_text("RENDER CONTROLS",position=(.08,.94),viewport=True,
                        font_size=13,color="#e4edf8")
        self.status = self.p.add_text("Paused · fixed physical scales",position=(.08,.895),
                                      viewport=True,font_size=9,color="#70d6df")
        controls = [
            ("density_max","Density scale (1e22 m^-3)",(.2,10.),1e22,.81,"%.2f"),
            ("opacity","Plasma opacity",(0.,1.),1.,.71,"%.2f"),
            ("density_cutoff","Hide low density (fraction)",(0.,.5),1.,.61,"%.2f"),
            ("smoothing_z_cm","Axial smoothing (cm)",(0.,1.5),1.,.51,"%.2f"),
            ("line_opacity","Field-line opacity",(0.,1.),1.,.41,"%.2f"),
            ("line_density","Field-line detail",(1.,8.),1.,.31,"%.0f"),
            ("geometry_opacity","Device opacity",(0.,.5),1.,.21,"%.2f"),
        ]
        for name,title,rng,scale,y,fmt in controls:
            widget = self.p.add_slider_widget(
                lambda v,n=name,u=scale:self.set_value(n,v*u),rng,
                value=getattr(settings,name)/scale,title=title,
                pointa=(.12,y),pointb=(.88,y),style="modern",
                color="#67dbe8",title_color="#c9d6e5",title_height=.016,
                slider_width=.013,tube_width=.003,fmt=fmt,interaction_event="end")
            # VTK widgets use normalized display coordinates, not subplot coordinates.
            rep=widget.GetRepresentation()
            rep.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
            rep.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
            rep.GetPoint1Coordinate().SetValue(.12*.24,y)
            rep.GetPoint2Coordinate().SetValue(.88*.24,y)
            rep.SetSliderLength(.025)
            rep.SetLabelHeight(.014)
            self.sliders[name]=widget
        for i,(name,label) in enumerate([("show_lines","Field lines"),
                                         ("show_geometry","Device"),
                                         ("show_zero_field","Bz = 0 surface"),
                                         ("auto_exposure","Auto exposure")]):
            row,col=divmod(i,2)
            y=.12-row*.045
            button=self.p.add_checkbox_button_widget(
                lambda v,n=name:self.set_value(n,bool(v)),value=getattr(settings,name),
                position=((.07+col*.46)*size[0]*.24,y*size[1]),size=18,border_size=2,
                color_on="#67dbe8",color_off="#334458",background_color="#101a28")
            self.buttons[name]=button
            self.p.add_text(label,position=(.13+col*.46,y+.004),viewport=True,
                            font_size=8,color="#bdccdc")
        for key,cb in [
            ("space",self.toggle_play),("p",self.toggle_play),
            ("Left",lambda:self.step(-1)),("Right",lambda:self.step(1)),
            ("r",lambda:self.set_camera("presentation")),
            ("1",lambda:self.set_camera("presentation")),
            ("2",lambda:self.set_camera("side")),("3",lambda:self.set_camera("end")),
            ("s",self.screenshot),("w",self.save_settings)]:
            self.p.add_key_event(key,cb)
        self.p.iren.add_observer("ConfigureEvent",self.resize_controls)
        self.p.subplot(0,0)
        self.ready=True
        self.draw()

    def set_value(self,name,value):
        if not self.ready:
            return
        if name=="line_density":
            value=int(round(value))
        setattr(self.settings,name,value)
        self.settings.validate()
        self.draw()

    def resize_controls(self,*_):
        width,height=self.p.window_size
        for i,button in enumerate(self.buttons.values()):
            row,col=divmod(i,2)
            x=(.07+col*.46)*width*.24
            y=(.12-row*.045)*height
            button.GetRepresentation().PlaceWidget((x,x+18,y,y+18,0,0))

    def set_camera(self,name):
        self.p.subplot(0,0)
        self.settings.camera=name
        self.settings.camera_position=None
        self.settings.parallel_scale=17. if name!="end" else 4.
        self.scene.apply_camera()
        self.p.render()

    def seek(self,value):
        if self.ready:
            self.k=int(np.abs(self.times-value).argmin())
            self.draw()

    def step(self,direction):
        self.k=(self.k+direction)%len(self.frames)
        self.draw()

    def toggle_play(self):
        self.playing=not self.playing
        self.last_tick=time.monotonic()
        self.draw()

    def tick(self,*_):
        now=time.monotonic()
        if self.playing and now-self.last_tick >= 1/self.settings.fps:
            self.last_tick=now
            self.step(1)

    def draw(self):
        self.p.subplot(0,0)
        self.scene.draw(self.frames[self.k],render=False)
        self.time_slider.GetRepresentation().SetValue(self.times[self.k])
        mode="adaptive density" if self.settings.auto_exposure else "fixed physical scales"
        self.status.input=f"{'Playing' if self.playing else 'Paused'} · {mode}\nOutput {self.k+1} / {len(self.frames)}"
        self.p.render()

    def _path(self,suffix):
        self.output_dir.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return self.output_dir/f"{self.run_dir.name}-{stamp}{suffix}"

    def save_settings(self):
        self.p.subplot(0,0)
        self.scene.capture_camera()
        path=self._path(".settings.json")
        self.settings.save(path)
        self.status.input=f"Settings saved\n{path.name}"
        print(path,flush=True)
        self.p.render()
        return path

    def screenshot(self):
        from yingguang_frc.visualization.animate import render_image
        self.playing=False
        self.p.subplot(0,0)
        self.scene.capture_camera()
        path=self._path(".png")
        # Save a clean high-quality scene without the interactive control panel.
        render_image(self.frames,replace(self.settings,quality="high"),self.run_dir,path)
        self.settings.save(path.with_suffix(".settings.json"))
        self.status.input=f"Image + settings saved\n{path.name}"
        print(path,flush=True)
        self.p.render()
        return path

    def run(self):
        self.p.add_timer_event(max_steps=10**9,duration=30,callback=self.tick)
        self.p.show()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir",type=Path)
    ap.add_argument("--settings",type=Path)
    ap.add_argument("--quality",choices=QUALITY)
    ap.add_argument("--output-dir",type=Path,default=Path("results/local/viewer"))
    ap.add_argument("--size",type=int,nargs=2,default=(1600,900))
    ap.add_argument("--stride",type=int,default=1)
    ap.add_argument("--fps",type=float)
    ap.add_argument("--time-us",type=float)
    ap.add_argument("--n-max",type=float)
    ap.add_argument("--b-max",type=float)
    ap.add_argument("--no-lines",action="store_true")
    ap.add_argument("--off-screen",action="store_true",help="Render the UI to PNG and exit")
    args=ap.parse_args()
    try:
        if args.stride<1 or min(args.size)<400:
            raise ValueError("stride must be positive; window dimensions must be at least 400")
        settings=RenderSettings.load(args.settings) if args.settings else RenderSettings()
        for arg,key in [(args.quality,"quality"),(args.fps,"fps"),(args.time_us,"time_us"),
                        (args.n_max,"density_max"),(args.b_max,"magnetic_max")]:
            if arg is not None:
                setattr(settings,key,arg)
        if args.no_lines:
            settings.show_lines=False
        settings.validate()
        frames=select_frames(load_series(args.run_dir),args.stride)
        viewer=Viewer(frames,settings,args.run_dir,args.output_dir,args.size,args.off_screen)
        if args.off_screen:
            path=viewer._path("-ui.png")
            viewer.p.screenshot(str(path))
            viewer.p.close()
            print(path)
        else:
            viewer.run()
    except (OSError,ValueError) as error:
        ap.error(str(error))


if __name__=="__main__":
    main()

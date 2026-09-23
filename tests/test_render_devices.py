"""Synthetic device-policy tests, not GPU hardware acceptance."""
import importlib
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from asset_director.core import DirectorError
from asset_director.render_devices import selection, require_observed

class DeviceTests(unittest.TestCase):
    def test_default_and_explicit_cpu(self):
        self.assertEqual(selection({}), {"backend":"CPU"})
        self.assertEqual(selection({"render_device":{"backend":"CPU"}}), {"backend":"CPU"})
        require_observed(selection({}), {})  # Old readiness.
    def test_bad_device_options(self):
        for value in [None, [], "OPTIX", {}, {"backend":"AUTO"}, {"backend":"CUDA"},
                      {"backend":"CPU","id":"x"}, {"backend":"OPTIX"}, {"backend":"OPTIX","id":True},
                      {"backend":"OPTIX","id":"x\n"}, {"backend":"OPTIX","id":"x","script":"x"}]:
            with self.subTest(value=value), self.assertRaises(DirectorError):
                selection({"render_device":value})
    def test_exact_readiness_identity_and_duplicates(self):
        gpu={"backend":"OPTIX","id":"observed"};audit={"render_devices":[{**gpu,"name":"Synthetic GPU"}]}
        require_observed(gpu,audit)
        for invalid in [{},{"render_devices":[{"backend":"OPTIX","id":"other"}]},
                        {"render_devices":audit["render_devices"]*2}]:
            with self.assertRaises(DirectorError):require_observed(gpu,invalid)

class BlenderDevicePolicyTests(unittest.TestCase):
    def setUp(self):
        self.devices=[NS(type="CPU",id="cpu",name="Synthetic CPU",use=True),
                      NS(type="OPTIX",id="gpu1",name="Synthetic GPU 1",use=False),
                      NS(type="OPTIX",id="gpu2",name="Synthetic GPU 2",use=True)]
        self.prefs=NS(devices=self.devices,compute_device_type="NONE",
                      get_device_types=lambda context:[("NONE",),("OPTIX",)],
                      get_devices_for_type=lambda backend:self.devices)
        self.cycles=NS(device="CPU",use_denoising=True,denoiser="OPENIMAGEDENOISE",denoising_use_gpu=False)
        self.fake=NS(app=NS(background=True,version_string="synthetic"),
                     context=NS(preferences=NS(addons={"cycles":NS(preferences=self.prefs)}),
                                scene=NS(cycles=self.cycles,render=NS(threads=20,threads_mode="AUTO"))))
        with patch.dict(sys.modules,{"bpy":self.fake}):
            self.module=importlib.import_module("asset_director.render_devices_blender")
        self.binding=patch.object(self.module,"bpy",self.fake);self.binding.start();self.addCleanup(self.binding.stop)
        self.audit={"render_devices":[{"backend":"OPTIX","id":"gpu1","name":"Synthetic GPU 1"}]}
        self.options={"render_device":{"backend":"OPTIX","id":"gpu1"}}
    def test_only_exact_gpu_enabled_with_gpu_denoising(self):
        result=self.module.configure(self.options,self.audit)
        self.assertEqual([d.id for d in self.devices if d.use],["gpu1"])
        self.assertEqual(self.cycles.device,"GPU");self.assertEqual(self.cycles.denoiser,"OPTIX")
        self.assertEqual(result["backend"],"OPTIX");self.assertFalse(result["fallback"])
        self.assertEqual(self.fake.context.scene.render.threads,2)
    def test_cpu_disables_gpu_denoising_without_changing_method(self):
        self.cycles.denoising_use_gpu=True
        result=self.module.configure({}, {})
        self.assertEqual(result["backend"],"CPU");self.assertFalse(self.cycles.denoising_use_gpu)
        self.assertEqual(self.cycles.denoiser,"OPENIMAGEDENOISE")
    def test_missing_or_disappeared_gpu_refused_no_cpu_retry(self):
        self.prefs.get_devices_for_type=lambda backend:[]
        with self.assertRaises(DirectorError):self.module.configure(self.options,self.audit)
        self.assertEqual(self.cycles.device,"CPU") # Failed before applying/rendering.
    def test_discovery_error_keeps_cpu_but_gpu_request_fails(self):
        def unavailable(backend):raise RuntimeError("Synthetic driver failure")
        self.prefs.get_devices_for_type=unavailable
        devices,warnings=self.module.discover()
        self.assertEqual([d["backend"] for d in devices],["CPU"]);self.assertTrue(warnings)
        with self.assertRaises(DirectorError):self.module.configure(self.options,self.audit)
    def test_no_foreground_preferences_mutation(self):
        self.fake.app.background=False
        with self.assertRaises(DirectorError):self.module.configure(self.options,self.audit)
        self.assertEqual(self.prefs.compute_device_type,"NONE")
    def test_device_drift_refused(self):
        result=self.module.configure(self.options,self.audit)
        self.devices[0].use=True
        with self.assertRaises(DirectorError):self.module.evidence(self.options["render_device"],result["name"])
    def test_disabled_denoising_stays_disabled(self):
        self.cycles.use_denoising=False
        result=self.module.configure(self.options,self.audit)
        self.assertFalse(result["denoising"]["enabled"])
        self.assertEqual(self.cycles.denoiser,"OPENIMAGEDENOISE")

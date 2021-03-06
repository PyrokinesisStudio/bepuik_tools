# ====================== BEGIN GPL LICENSE BLOCK ======================
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#  The Original Code is Copyright (C) 2013 by: 
#  Harrison Nordby and Ross Nordby
#  All rights reserved.
#
#  The Original Code is: all of this file, except for root widget
#  pydata taken from Rigify's utils.py
#
#  Contributor(s): none yet.
#
#
#======================= END GPL LICENSE BLOCK ========================

import bpy

from mathutils import Vector, Matrix, geometry
from rna_prop_ui import rna_idprop_ui_prop_get

import math
import inspect
import re

AL_ANIMATABLE = 0
AL_TARGET = 1
AL_DEFORMER = 2
AL_MECHANICAL = 3
AL_BEPUIK_BONE = 4

AL_SPINE = 17
AL_HEAD = 16
AL_ROOT = 18
AL_FACE = 19

AL_ARM_L = 8
AL_HAND_L = 9
AL_LEG_L = 10
AL_FOOT_L = 11
AL_RIB_L = 12

AL_ARM_R = AL_ARM_L + 16
AL_HAND_R = AL_HAND_L + 16
AL_LEG_R = AL_LEG_L + 16
AL_FOOT_R = AL_FOOT_L + 16
AL_RIB_R = AL_RIB_L + 16

AL_START = {AL_ARM_L, AL_ARM_R, AL_LEG_L, AL_LEG_R, AL_SPINE, AL_HEAD, AL_HAND_L, AL_HAND_R, AL_FOOT_L, AL_FOOT_R}

BEPUIK_BALL_SOCKET_RIGIDITY_DEFAULT = 16

#put bones containing the following substrings on different layers depending on the bone's suffix letter
ARM_SUBSTRINGS = ('shoulder', 'loarm', 'uparm', 'hand', 'elbow',)
LEG_SUBSTRINGS = ('leg', 'foot', 'knee', 'heel', 'ball',)
FOOT_SUBSTRINGS = ('toe',)
TORSO_SUBSTRINGS = ('spine', 'hip', 'chest', 'torso', 'tail', 'belly', 'back', 'groin')
RIB_SUBSTRINGS = ('rib', 'clavicle')
HAND_SUBSTRINGS = ('finger', 'thumb', 'palm')

#put bones containing the following substrings on same layer regardless of bone's suffix letter
HEAD_SUBSTRINGS = ('head', 'neck', 'eye target')
FACE_SUBSTRINGS = ('eye', 'jaw', 'ear', 'nose', 'brow', 'lip', 'chin', 'cheek', 'tongue', 'face')
ROOT_SUBSTRINGS = ('root',)
TARGET_SUBSTRINGS = ('target',)

SUBSTRING_SETS = [HAND_SUBSTRINGS, ARM_SUBSTRINGS, LEG_SUBSTRINGS, FOOT_SUBSTRINGS, TORSO_SUBSTRINGS, RIB_SUBSTRINGS,
                  HEAD_SUBSTRINGS, ROOT_SUBSTRINGS, TARGET_SUBSTRINGS, FACE_SUBSTRINGS]

MAP_SUBSTRING_SET_TO_ARMATURELAYER = {}

def map_substring_set(substring_set, suffixletter_layer_pairs):
    global MAP_SUBSTRING_SET_TO_ARMATURELAYER
    for suffixletter_layer_pair in suffixletter_layer_pairs:
        suffix, layer = suffixletter_layer_pair
        MAP_SUBSTRING_SET_TO_ARMATURELAYER[(substring_set, suffix)] = layer

def map_substring_set_all_suffix_go_to_same_layer(substring_set, layer):
    map_substring_set(substring_set, (('L', layer), ('R', layer), (None, layer), ('', layer)))

map_substring_set(ARM_SUBSTRINGS, (('L', AL_ARM_L), ('R', AL_ARM_R)))
map_substring_set(LEG_SUBSTRINGS, (('L', AL_LEG_L), ('R', AL_LEG_R)))
map_substring_set(FOOT_SUBSTRINGS, (('L', AL_FOOT_L), ('R', AL_FOOT_R)))
map_substring_set(RIB_SUBSTRINGS, (('L', AL_RIB_L), ('R', AL_RIB_R)))
map_substring_set(HAND_SUBSTRINGS, (('L', AL_HAND_L), ('R', AL_HAND_R)))


map_substring_set_all_suffix_go_to_same_layer(TORSO_SUBSTRINGS, AL_SPINE)
map_substring_set_all_suffix_go_to_same_layer(HEAD_SUBSTRINGS, AL_HEAD)
map_substring_set_all_suffix_go_to_same_layer(FACE_SUBSTRINGS, AL_FACE)
map_substring_set_all_suffix_go_to_same_layer(TARGET_SUBSTRINGS, AL_TARGET)
map_substring_set_all_suffix_go_to_same_layer(ROOT_SUBSTRINGS, AL_ROOT)

FINGER_TOE_RIGIDITY = 3

WIDGET_HAND = "widget hand"
WIDGET_SOLE = "widget sole"
WIDGET_BONE = "widget bone"
WIDGET_ROOT = "widget root"
WIDGET_EYE_TARGET = "widget eye target"
WIDGET_SPHERE = "widget sphere"
WIDGET_CUBE = "widget cube"
WIDGET_PAD = "widget pad"
WIDGET_CIRCLE = "widget circle"
WIDGET_FOOT = "widget foot"
WIDGET_FLOOR = "widget floor"
WIDGET_FLOOR_TARGET = "widget floor target"
WIDGET_FLOOR_L = "widget floor.L"
WIDGET_FLOOR_R = "widget floor.R"
WIDGET_FLOOR_TARGET_L = "widget floor target.L"
WIDGET_FLOOR_TARGET_R = "widget floor target.R"
WIDGET_TOES = "widget toes"
WIDGET_STIFF_CIRCLE = "widget stiff circle"
WIDGET_STIFF_TRIANGLE = "widget stiff triangle"
WIDGET_STIFF_SWITCH = "widget stiff switch"


class WidgetData():
    def __init__(self, vertices=None, edges=None, faces=None):
        if not faces:
            faces = []
        if not edges:
            edges = []
        if not vertices:
            vertices = []
        self.vertices = vertices
        self.edges = edges
        self.faces = faces
        self.subsurface_levels = 0
        self.ob = None

    def create_ob(self, name):
        mesh = bpy.data.meshes.new(name + " mesh")
        ob = bpy.data.objects.new(name, mesh)
        ob.data.from_pydata(self.vertices, self.edges, self.faces)
        ob.data.update()

        if self.subsurface_levels > 0:
            ob.modifiers.new(name="Subsurface", type='SUBSURF').levels = self.subsurface_levels

        self.ob = ob
        return ob

    def transform(self, transform):
        for i in range(len(self.vertices)):
            v = transform * Vector(self.vertices[i])
            self.vertices[i] = (v[0], v[1], v[2])


def widgetdata_circle(radius):
    widgetdata = WidgetData()
    vertices = [(0.7071068286895752, 0, -0.7071065306663513),
                (0.8314696550369263, 0, -0.5555699467658997),
                (0.9238795042037964, 0, -0.3826831877231598),
                (0.9807852506637573, 0, -0.19509011507034302),
                (1.0, 0, 0),
                (0.9807853698730469, 0, 0.19509044289588928),
                (0.9238796234130859, 0, 0.38268351554870605),
                (0.8314696550369263, 0, 0.5555704236030579),
                (0.7071068286895752, 0, 0.7071070075035095),
                (0.5555702447891235, 0, 0.8314698934555054),
                (0.38268327713012695, 0, 0.923879861831665),
                (0.19509008526802063, 0, 0.9807855486869812),
                (0, 0, 1),
                (-0.19509072601795197, 0, 0.9807854294776917),
                (-0.3826838731765747, 0, 0.9238795638084412),
                (-0.5555707216262817, 0, 0.8314695358276367),
                (-0.7071071863174438, 0, 0.7071065902709961),
                (-0.8314700126647949, 0, 0.5555698871612549),
                (-0.923879861831665, 0, 0.3826829195022583),
                (-0.9807853698730469, 0, 0.1950896978378296),
                (-1.0, 0, 0),
                (-0.9807850122451782, 0, -0.195091113448143),
                (-0.9238790273666382, 0, -0.38268423080444336),
                (-0.831468939781189, 0, -0.5555710196495056),
                (-0.7071058750152588, 0, -0.707107424736023),
                (-0.555569052696228, 0, -0.8314701318740845),
                (-0.38268208503723145, 0, -0.923879861831665),
                (-0.19508881866931915, 0, -0.9807853102684021),
                (0, 0, -1),
                (0.19509197771549225, 0, -0.9807847142219543),
                (0.3826850652694702, 0, -0.9238786101341248),
                (0.5555717945098877, 0, -0.8314683437347412)]
    widgetdata.edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11),
                        (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (17, 18), (18, 19), (19, 20),
                        (20, 21), (21, 22), (22, 23), (23, 24), (24, 25), (25, 26), (26, 27), (27, 28), (28, 29),
                        (29, 30), (30, 31), (0, 31)]
    widgetdata.faces = []
    widgetdata.vertices = [(v[0] * radius, v[1] * radius, v[2] * radius) for v in vertices]
    return widgetdata


def widgetdata_pad(width=1.0, length=1.0, mid=.5):
    widgetdata = WidgetData()
    hw = width / 2
    widgetdata.vertices = [(-hw, 0.0, 0.0), (-hw, mid, 0.0), (-hw, length, 0.0), (hw, length, 0.0), (hw, mid, 0.0),
                           (hw, 0.0, 0.0)]
    widgetdata.edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]
    widgetdata.faces = []
    widgetdata.subsurface_levels = 2
    return widgetdata


def widgetdata_refresh_defaults():
    for name, widget in WIDGET_DATA_DEFAULTS.items():
        if name in bpy.data.objects:
            widget.ob = bpy.data.objects[name]
        else:
            widget.ob = None

def unlink_ob_from_all_scenes(ob):
    for scene in bpy.data.scenes:
        if ob.name in scene.objects:
            scene.objects.unlink(ob)

def widgetdata_get(name, custom_widget_data=None):
    if name in bpy.data.objects:
        old_ob = bpy.data.objects[name]
    else:
        old_ob = None

    if custom_widget_data and name in custom_widget_data:
        widgetdata = custom_widget_data[name]
    elif name in WIDGET_DATA_DEFAULTS:
        widgetdata = WIDGET_DATA_DEFAULTS[name]
    else:
        widgetdata = None

    if widgetdata and not widgetdata.ob:
        if old_ob:
            old_ob.name += "old"
            unlink_ob_from_all_scenes(old_ob)

        assert isinstance(widgetdata, WidgetData)
        widgetdata.create_ob(name)
        new_ob = widgetdata.ob

        bpy.context.scene.objects.link(new_ob)
        new_ob.layers = OB_LAYERS_WIDGET
        return new_ob
    else:
        return old_ob


def pydata_get_edges(obj):
    return [(edge.vertices[0], edge.vertices[1]) for edge in obj.data.edges]


def pydata_get_vertices(obj):
    return [(v.co[0], v.co[1], v.co[2]) for v in obj.data.vertices]


def pydata_get_faces(obj):
    return [[v for v in p.vertices] for p in obj.data.polygons]


def quat_get_up(v):
    w = v.w
    x = v.x
    y = v.y
    z = v.z
    return Vector((2 * (x * z + w * y), 2 * (y * x - w * x), 1 - 2 * (x * x + y * y)))


def quat_get_forward(v):
    w = v.w
    x = v.x
    y = v.y
    z = v.z
    return Vector((2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)))


def quat_get_right(v):
    w = v.w
    x = v.x
    y = v.y
    z = v.z
    return Vector((1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)))


WIDGET_DATA_DEFAULTS = {}
wd = WIDGET_DATA_DEFAULTS[WIDGET_CUBE] = WidgetData()
wd.vertices = [(-1.0, -1.0, -1.0), (-1.0, 1.0, -1.0), (1.0, 1.0, -1.0), (1.0, -1.0, -1.0), (-1.0, -1.0, 1.0),
               (-1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, -1.0, 1.0)]
wd.edges = [(4, 5), (5, 1), (1, 0), (0, 4), (5, 6), (6, 2), (2, 1), (6, 7), (7, 3), (3, 2), (7, 4), (0, 3)]
wd.faces = []  #faces make bmesh wonky? not right format? [[4, 5, 1, 0], [5, 6, 2, 1], [6, 7, 3, 2], [7, 4, 0, 3], [0, 1, 2, 3], [7, 6, 5, 4]]

wd = WIDGET_DATA_DEFAULTS[WIDGET_SPHERE] = WidgetData()
wd.vertices = [(-0.3826834559440613, 0.0, 0.9238795638084412), (-0.7071068286895752, 0.0, 0.7071067690849304),
               (-0.9238795638084412, 0.0, 0.3826834261417389), (-1.0, 0.0, -4.371138828673793e-08),
               (-0.9238795042037964, 0.0, -0.38268351554870605), (-0.7071067690849304, 0.0, -0.7071067690849304),
               (-0.38268348574638367, 0.0, -0.9238795042037964), (-1.5099580252808664e-07, 0.0, -1.0),
               (-0.9238795042037964, 0.3826833665370941, -5.960464477539063e-08),
               (-0.7071067690849304, 0.7071065902709961, -5.960464477539063e-08),
               (-0.3826834559440613, 0.9238792657852173, -5.960464477539063e-08),
               (-1.2119348014039133e-07, 0.38268324732780457, 0.9238796234130859),
               (-1.5099580252808664e-07, 0.7071065902709961, 0.7071068286895752),
               (-1.2119348014039133e-07, 0.9238792657852173, 0.3826833963394165),
               (-1.2119348014039133e-07, 0.9999996423721313, -5.960464477539063e-08),
               (-1.2119348014039133e-07, 0.9238792657852173, -0.38268351554870605),
               (-1.3609464133423899e-07, 0.7071064710617065, -0.7071067690849304),
               (-1.3609464133423899e-07, 0.38268327713012695, -0.9238795042037964),
               (-2.08779383115143e-07, -1.395019069150294e-07, 1.0),
               (0.3826831579208374, 0.9238791465759277, -5.960464477539063e-08),
               (0.7071062922477722, 0.7071064710617065, -5.960464477539063e-08),
               (0.9238789081573486, 0.3826832175254822, -5.960464477539063e-08),
               (0.38268303871154785, -2.9802322387695312e-08, 0.9238796234130859),
               (0.7071062922477722, -1.4901161193847656e-08, 0.7071068286895752),
               (0.9238789677619934, -8.940696716308594e-08, 0.3826833963394165),
               (0.9999992847442627, -2.9802322387695312e-08, -5.960464477539063e-08),
               (0.9238789677619934, -8.940696716308594e-08, -0.38268351554870605),
               (0.7071061730384827, -2.9802322387695312e-08, -0.7071067690849304),
               (0.38268303871154785, -2.9802322387695312e-08, -0.9238795042037964),
               (0.9238788485527039, -0.38268324732780457, -5.960464477539063e-08),
               (0.7071061730384827, -0.7071064114570618, -5.960464477539063e-08),
               (0.38268303871154785, -0.9238789677619934, -5.960464477539063e-08),
               (-1.658969637219343e-07, -0.3826831579208374, 0.9238796234130859),
               (-1.8079812491578195e-07, -0.707106351852417, 0.7071068286895752),
               (-2.4040275548031786e-07, -0.9238789677619934, 0.3826833963394165),
               (-1.8079812491578195e-07, -0.9999993443489075, -5.960464477539063e-08),
               (-2.4040275548031786e-07, -0.9238789677619934, -0.38268351554870605),
               (-1.658969637219343e-07, -0.707106351852417, -0.7071067690849304),
               (-1.658969637219343e-07, -0.3826831579208374, -0.9238795042037964),
               (-0.3826833665370941, -0.9238789081573486, -5.960464477539063e-08),
               (-0.7071065306663513, -0.7071062326431274, -5.960464477539063e-08),
               (-0.923879086971283, -0.3826830983161926, -5.960464477539063e-08)]
wd.edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (3, 8), (8, 9), (9, 10), (11, 12), (12, 13),
            (13, 14), (14, 15), (15, 16), (16, 17), (10, 14), (14, 19), (19, 20), (20, 21), (22, 23), (23, 24),
            (24, 25),
            (25, 26), (26, 27), (27, 28), (21, 25), (25, 29), (29, 30), (30, 31), (32, 33), (33, 34), (34, 35),
            (35, 36),
            (36, 37), (37, 38), (31, 35), (35, 39), (39, 40), (40, 41), (18, 0), (18, 11), (17, 7), (18, 22), (28, 7),
            (18, 32), (38, 7), (41, 3)]
wd.faces = []

wd = WIDGET_DATA_DEFAULTS[WIDGET_EYE_TARGET] = WidgetData()
wd.vertices = [(-0.5, 2.9802322387695312e-08, 0.5), (-0.5975451469421387, 2.9802322387695312e-08, 0.49039262533187866),
               (-0.691341757774353, 2.9802322387695312e-08, 0.4619397819042206),
               (-0.7777851223945618, 2.9802322387695312e-08, 0.41573479771614075),
               (-0.8535534143447876, 2.9802322387695312e-08, 0.3535533845424652),
               (-0.9157347679138184, 2.9802322387695312e-08, 0.2777850925922394),
               (-0.961939811706543, 1.4901161193847656e-08, 0.19134171307086945),
               (-0.9903926253318787, 7.450580596923828e-09, 0.09754517674446106),
               (-1.0, 3.552713678800501e-15, 3.774895063202166e-08),
               (-0.9903926849365234, -7.450580596923828e-09, -0.09754510223865509),
               (-0.961939811706543, -1.4901161193847656e-08, -0.19134163856506348),
               (-0.9157348275184631, -2.9802322387695312e-08, -0.2777850925922394),
               (-0.8535534143447876, -2.9802322387695312e-08, -0.3535533845424652),
               (-0.777785062789917, -2.9802322387695312e-08, -0.41573482751846313),
               (-0.6913416385650635, -2.9802322387695312e-08, -0.4619397819042206),
               (-0.5975450277328491, -2.9802322387695312e-08, -0.49039265513420105),
               (-0.49999985098838806, -2.9802322387695312e-08, -0.5),
               (-0.4024546444416046, -2.9802322387695312e-08, -0.4903925955295563),
               (-0.30865806341171265, -2.9802322387695312e-08, -0.4619396924972534),
               (-0.22221463918685913, -2.9802322387695312e-08, -0.4157346487045288),
               (-0.1464463770389557, -2.9802322387695312e-08, -0.3535531461238861),
               (-0.08426499366760254, -2.9802322387695312e-08, -0.2777848243713379),
               (-0.03806006908416748, -1.4901161193847656e-08, -0.1913413405418396),
               (-0.009607285261154175, -7.450580596923828e-09, -0.09754472970962524),
               (0.0, 5.684341886080802e-14, 4.827995780942729e-07),
               (-0.009607464075088501, 7.450580596923828e-09, 0.09754567593336105),
               (-0.03806045651435852, 1.4901161193847656e-08, 0.19134223461151123),
               (-0.08426553010940552, 2.9802322387695312e-08, 0.27778562903404236),
               (-0.1464470624923706, 2.9802322387695312e-08, 0.3535538613796234),
               (-0.2222154438495636, 2.9802322387695312e-08, 0.4157351851463318),
               (-0.3086589574813843, 2.9802322387695312e-08, 0.46194005012512207),
               (-0.402455598115921, 2.9802322387695312e-08, 0.490392804145813), (0.5, 2.9802322387695312e-08, 0.5),
               (0.40245485305786133, 2.9802322387695312e-08, 0.49039262533187866),
               (0.308658242225647, 2.9802322387695312e-08, 0.4619397819042206),
               (0.22221487760543823, 2.9802322387695312e-08, 0.41573479771614075),
               (0.1464465856552124, 2.9802322387695312e-08, 0.3535533845424652),
               (0.08426523208618164, 2.9802322387695312e-08, 0.2777850925922394),
               (0.03806018829345703, 1.4901161193847656e-08, 0.19134171307086945),
               (0.009607374668121338, 7.450580596923828e-09, 0.09754517674446106),
               (0.0, 3.552713678800501e-15, 3.774895063202166e-08),
               (0.009607315063476562, -7.450580596923828e-09, -0.09754510223865509),
               (0.03806018829345703, -1.4901161193847656e-08, -0.19134163856506348),
               (0.08426517248153687, -2.9802322387695312e-08, -0.2777850925922394),
               (0.1464465856552124, -2.9802322387695312e-08, -0.3535533845424652),
               (0.222214937210083, -2.9802322387695312e-08, -0.41573482751846313),
               (0.3086583614349365, -2.9802322387695312e-08, -0.4619397819042206),
               (0.4024549722671509, -2.9802322387695312e-08, -0.49039265513420105),
               (0.5000001192092896, -2.9802322387695312e-08, -0.5),
               (0.5975453853607178, -2.9802322387695312e-08, -0.4903925955295563),
               (0.6913419365882874, -2.9802322387695312e-08, -0.4619396924972534),
               (0.7777853608131409, -2.9802322387695312e-08, -0.4157346487045288),
               (0.8535536527633667, -2.9802322387695312e-08, -0.3535531461238861),
               (0.9157350063323975, -2.9802322387695312e-08, -0.2777848243713379),
               (0.9619399309158325, -1.4901161193847656e-08, -0.1913413405418396),
               (0.9903926849365234, -7.450580596923828e-09, -0.09754472970962524),
               (1.0, 5.684341886080802e-14, 4.827995780942729e-07),
               (0.9903925657272339, 7.450580596923828e-09, 0.09754567593336105),
               (0.9619395732879639, 1.4901161193847656e-08, 0.19134223461151123),
               (0.9157344698905945, 2.9802322387695312e-08, 0.27778562903404236),
               (0.8535529375076294, 2.9802322387695312e-08, 0.3535538613796234),
               (0.7777845859527588, 2.9802322387695312e-08, 0.4157351851463318),
               (0.6913410425186157, 2.9802322387695312e-08, 0.46194005012512207),
               (0.5975444316864014, 2.9802322387695312e-08, 0.490392804145813)]
wd.edges = [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4), (6, 5), (7, 6), (8, 7), (9, 8), (10, 9), (11, 10), (12, 11),
            (13, 12), (14, 13), (15, 14), (16, 15), (17, 16), (18, 17), (19, 18), (20, 19), (21, 20), (22, 21),
            (23, 22), (24, 23), (25, 24), (26, 25), (27, 26), (28, 27), (29, 28), (30, 29), (31, 30), (0, 31), (33, 32),
            (34, 33),
            (35, 34), (36, 35), (37, 36), (38, 37), (39, 38), (40, 39), (41, 40), (42, 41), (43, 42), (44, 43),
            (45, 44), (46, 45), (47, 46), (48, 47), (49, 48), (50, 49), (51, 50), (52, 51), (53, 52), (54, 53),
            (55, 54), (56, 55),
            (57, 56), (58, 57), (59, 58), (60, 59), (61, 60), (62, 61), (63, 62), (32, 63)]
wd.faces = []

wd = WIDGET_DATA_DEFAULTS[WIDGET_ROOT] = WidgetData()
wd.vertices = [(0.7071067690849304, 0.7071067690849304, 0.0), (0.7071067690849304, -0.7071067690849304, 0.0),
               (-0.7071067690849304, 0.7071067690849304, 0.0), (-0.7071067690849304, -0.7071067690849304, 0.0),
               (0.8314696550369263, 0.5555701851844788, 0.0), (0.8314696550369263, -0.5555701851844788, 0.0),
               (-0.8314696550369263, 0.5555701851844788, 0.0), (-0.8314696550369263, -0.5555701851844788, 0.0),
               (0.9238795042037964, 0.3826834261417389, 0.0), (0.9238795042037964, -0.3826834261417389, 0.0),
               (-0.9238795042037964, 0.3826834261417389, 0.0), (-0.9238795042037964, -0.3826834261417389, 0.0),
               (0.9807852506637573, 0.19509035348892212, 0.0), (0.9807852506637573, -0.19509035348892212, 0.0),
               (-0.9807852506637573, 0.19509035348892212, 0.0), (-0.9807852506637573, -0.19509035348892212, 0.0),
               (0.19509197771549225, 0.9807849526405334, 0.0), (0.19509197771549225, -0.9807849526405334, 0.0),
               (-0.19509197771549225, 0.9807849526405334, 0.0), (-0.19509197771549225, -0.9807849526405334, 0.0),
               (0.3826850652694702, 0.9238788485527039, 0.0), (0.3826850652694702, -0.9238788485527039, 0.0),
               (-0.3826850652694702, 0.9238788485527039, 0.0), (-0.3826850652694702, -0.9238788485527039, 0.0),
               (0.5555717945098877, 0.8314685821533203, 0.0), (0.5555717945098877, -0.8314685821533203, 0.0),
               (-0.5555717945098877, 0.8314685821533203, 0.0), (-0.5555717945098877, -0.8314685821533203, 0.0),
               (0.19509197771549225, 1.2807848453521729, 0.0), (0.19509197771549225, -1.2807848453521729, 0.0),
               (-0.19509197771549225, 1.2807848453521729, 0.0), (-0.19509197771549225, -1.2807848453521729, 0.0),
               (1.280785322189331, 0.19509035348892212, 0.0), (1.280785322189331, -0.19509035348892212, 0.0),
               (-1.280785322189331, 0.19509035348892212, 0.0), (-1.280785322189331, -0.19509035348892212, 0.0),
               (0.3950919806957245, 1.2807848453521729, 0.0), (0.3950919806957245, -1.2807848453521729, 0.0),
               (-0.3950919806957245, 1.2807848453521729, 0.0), (-0.3950919806957245, -1.2807848453521729, 0.0),
               (1.280785322189331, 0.39509034156799316, 0.0), (1.280785322189331, -0.39509034156799316, 0.0),
               (-1.280785322189331, 0.39509034156799316, 0.0), (-1.280785322189331, -0.39509034156799316, 0.0),
               (0.0, 1.5807849168777466, 0.0), (0.0, -1.5807849168777466, 0.0), (1.5807852745056152, 0.0, 0.0),
               (-1.5807852745056152, 0.0, 0.0)]
wd.edges = [(0, 4), (1, 5), (2, 6), (3, 7), (4, 8), (5, 9), (6, 10), (7, 11), (8, 12), (9, 13), (10, 14), (11, 15),
            (16, 20), (17, 21), (18, 22), (19, 23), (20, 24), (21, 25), (22, 26), (23, 27), (0, 24), (1, 25), (2, 26),
            (3, 27), (16, 28), (17, 29), (18, 30), (19, 31), (12, 32), (13, 33), (14, 34), (15, 35), (28, 36), (29, 37),
            (30, 38), (31, 39), (32, 40), (33, 41), (34, 42), (35, 43), (36, 44), (37, 45), (38, 44), (39, 45),
            (40, 46),
            (41, 46), (42, 47), (43, 47)]
wd.faces = []

wd = WIDGET_DATA_DEFAULTS[WIDGET_BONE] = WidgetData()
wd.vertices = [(-.1, 0, -.1), (-.1, 1.0, -.1), (.1, 1.0, -.1), (.1, 0, -.1), (-.1, 0, .1), (-.1, 1.0, .1),
               (.1, 1.0, .1),
               (.1, 0, .1)]
wd.edges = [(4, 5), (5, 1), (1, 0), (0, 4), (5, 6), (6, 2), (2, 1), (6, 7), (7, 3), (3, 2), (7, 4), (0, 3)]
wd.faces = []

wd = WIDGET_DATA_DEFAULTS[WIDGET_STIFF_TRIANGLE] = WidgetData()
th = .6
tsl = .2
wd.vertices = [(-.1, th, -.1), (0, th, .2), (.1, th, -.1), (0, .1, -.1), (0, 1, -.1)]
wd.edges = [(0, 1), (1, 2), (2, 0), (3, 4)]
wd.faces = []

wd = WIDGET_DATA_DEFAULTS[WIDGET_STIFF_CIRCLE] = widgetdata_circle(.2)
wd.transform(Matrix.Translation(Vector((0, .6, 0))))
num_verts = len(wd.vertices)
wd.vertices.append((0, .1, -.1))
wd.vertices.append((0, 1, -.1))
wd.edges.append((num_verts, num_verts + 1))

wd = WIDGET_DATA_DEFAULTS[WIDGET_STIFF_SWITCH] = WidgetData()
wd.vertices = [(0, 0, .25), (0, 0, 0), (0, 1, 0), (0, 1, .25)]
wd.edges = [(0, 1), (1, 2), (2, 3)]
wd.faces = []


#w = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR] = WidgetData()
#w.vertices = [(-1,-.25,0),(-1,1,0),(1,1,0),(1,-.25,0)]
#w.edges = [(0,1),(1,2),(2,3),(3,0)]
#w.faces = []
#
#w = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_L] = WidgetData()
#w.vertices = [(-2,0,0),(-2,1,0),(-1,2,0),(.25,2,0),(.25,-2,0),(-1,-2,0),(-2,-1,0)]
#w.edges = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,0)]
#w.faces = []
#
#w = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_R] = WidgetData()
#w.vertices = [(t[0]*-1,t[1],t[2]) for t in WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_L].vertices]
#w.edges = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_L].edges[:]
#w.faces = []
#
#w = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_TARGET_L] = WidgetData()
#w.vertices = [(v[0],v[1]*1.3,v[2]) for v in WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_L].vertices]
#w.edges = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_L].edges[:]
#w.faces = []
#w.subsurface_levels = 2
#
#w = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_TARGET_R] = WidgetData()
#w.vertices = [(v[0]*1.1,v[1]*1.3,v[2]) for v in WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_R].vertices]
#w.edges = WIDGET_DATA_DEFAULTS[WIDGET_FLOOR_R].edges[:]
#w.faces = []
#w.subsurface_levels = 2

_metabone_root = None
_recognized_suffix_letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_recognized_suffix_delimiters = ('_', '.', '-', ' ')

OB_LAYERS_WIDGET = [False if i < 19 else True for i in range(20)]


def apply_rig_starting_layers(obj):
    obj.data.layers = [True if i in AL_START else False for i in range(32)]


def layout_rig_layers(layout, ob):
    data = ob.data

    box1 = layout.box()
    box1.label("Animation Bones")
    box1.prop(data, 'layers', toggle=True, index=AL_ANIMATABLE, text="All")

    top = box1.column(align=True)

    top.prop(data, 'layers', toggle=True, index=AL_FACE, text="Face")
    top.prop(data, 'layers', toggle=True, index=AL_HEAD, text="Head")
    top.prop(data, 'layers', toggle=True, index=AL_SPINE, text="Spine")
    top.prop(data, 'layers', toggle=True, index=AL_ROOT, text="Root")

    middle = box1.row()

    col = middle.column(align=True)
    col.label("Left")
    col.prop(data, 'layers', toggle=True, index=AL_ARM_L, text="Arm")
    col.prop(data, 'layers', toggle=True, index=AL_HAND_L, text="Fingers")
    col.prop(data, 'layers', toggle=True, index=AL_LEG_L, text="Leg")
    col.prop(data, 'layers', toggle=True, index=AL_FOOT_L, text="Toes")
    col.prop(data, 'layers', toggle=True, index=AL_RIB_L, text="Ribs")

    col = middle.column(align=True)
    col.label("Right")
    col.prop(data, 'layers', toggle=True, index=AL_ARM_R, text="Arm")
    col.prop(data, 'layers', toggle=True, index=AL_HAND_R, text="Fingers")
    col.prop(data, 'layers', toggle=True, index=AL_LEG_R, text="Leg")
    col.prop(data, 'layers', toggle=True, index=AL_FOOT_R, text="Toes")
    col.prop(data, 'layers', toggle=True, index=AL_RIB_R, text="Ribs")

    box2 = layout.box()
    box2.label("Other")
    col = box2.column(align=True)
    col.prop(data, 'layers', toggle=True, index=AL_TARGET, text="Targets")
    col.prop(data, 'layers', toggle=True, index=AL_DEFORMER, text="Deformers")
    col.prop(data, 'layers', toggle=True, index=AL_MECHANICAL, text="Mechanical")
    col.prop(data, 'layers', toggle=True, index=AL_BEPUIK_BONE, text="BEPUik Bones")

    layout.prop(ob, "show_x_ray")
    layout.prop(data, "show_bepuik_controls")


def split_suffix(s):
    possible_suffix = s[-2:]
    if possible_suffix[0] in _recognized_suffix_delimiters and possible_suffix[1] in _recognized_suffix_letters:
        return s[:-2], possible_suffix

    return s, ''


def get_suffix_letter(s):
    presuffix, suffix = split_suffix(s)

    if suffix:
        return suffix[1]

    return None


_blender_struct_attrs = {item[0] for item in inspect.getmembers(bpy.types.Struct)}


def get_rig_relevant_attr_names(ob):
    global _blender_struct_attrs
    return {item[0] for item in inspect.getmembers(ob)
            if item[0] not in _blender_struct_attrs | {'__qualname__', '__weakref__', '__dict__'}
            if not hasattr(getattr(ob, item[0]), '__call__')}


class MetaBlenderConstraint():
    def __init__(self, type, name=None):
        self.type = type
        self.name = name

    def apply_data_to_pchan(self, pbone):
        constraint = pbone.constraints.new(type=self.type)

        excluded_attr_names = {'name', 'type', 'connection_a', 'connection_b', 'target', 'subtarget', 'rigidity'}
        angle_attr_names = {'max_swing', 'max_twist'}

        #get the attributes that associate with important attributes in a blender constraint
        self_attr_names = get_rig_relevant_attr_names(self)
        self_attr_names -= excluded_attr_names

        constraint.name = self.name

        if constraint.is_bepuik:
            #we know that the bepuik constraint's object targets should always be the context object
            constraint.connection_target = bpy.context.object

            #the pchan containing the constraint is always considered connection a
            #therefore the connection subtarget is always connection b
            constraint.connection_subtarget = self.connection_b.name

            if hasattr(self, 'rigidity'):
                constraint.bepuik_rigidity = self.rigidity

            for attr_name in self_attr_names:
                dodefault = False
                val = getattr(self, attr_name)
                typeofval = type(val)
                #                print(pbone,constraint,attr_name,val)
                if attr_name in angle_attr_names:
                    #rig generation code always uses degrees, so we need to convert
                    setattr(constraint, attr_name, math.radians(val))
                elif typeofval is MetaBone:
                    '''
                    Blender constraints use a string to point to bones, but this
                    rig generation code doesn't use strings, it uses a Metabone object.
                    We can get the needed blender bone name from the metabone.name attribute
                    
                    Also, the rig generation code is concise, and leaves off the _subtarget suffix,
                    so it has to be reapplied to set the proper blender python attribute
                    '''
                    setattr(constraint, attr_name + "_subtarget", val.name)
                    setattr(constraint, attr_name + "_target", bpy.context.object)
                elif typeofval is list or typeofval is tuple:
                    mytuple = val

                    if type(val[0]) == MetaBone:
                        val1type = type(val[1])

                        if val1type == str:
                            #axis using bone as reference
                            setattr(constraint, attr_name + "_target", bpy.context.object)
                            setattr(constraint, attr_name + "_subtarget", val[0].name)
                            setattr(constraint, attr_name, val[1])
                        elif val1type == int or val1type == float:
                            #point using bone as reference
                            setattr(constraint, attr_name + "_target", bpy.context.object)
                            setattr(constraint, attr_name + "_subtarget", val[0].name)
                            setattr(constraint, attr_name + "_head_tail", val[1])
                        else:
                            dodefault = True
                    else:
                        dodefault = True
                else:
                    dodefault = True

                if dodefault:
                    try:
                        setattr(constraint, attr_name, val)
                    except:
                        raise Exception("""Don't know what to do with:
                                            pbone:%s
                                            constraint:%s
                                            attr:%s
                                            val:%s""" % (pbone.name, constraint.name, attr_name, val))

        else:
            if hasattr(constraint, "target"):
                if not hasattr(self, "target"):
                    constraint.target = bpy.context.object

            if hasattr(constraint, "subtarget"):
                if not hasattr(self, "subtarget"):
                    if hasattr(self, "connection_b"):
                        constraint.subtarget = self.connection_b.name

            for attr_name in self_attr_names:
                setattr(constraint, attr_name, getattr(self, attr_name))


def safesetattr(ob, attr, val):
    if isinstance(val, Vector):
        val = val.copy()

    setattr(ob, attr, val)


def vector_is_zero(vec, epsilon=0.000001):
    for v in vec:
        if abs(v) > epsilon:
            return False

    return True


def vector4_to_vector3(v4):
    return Vector((v4[0], v4[1], v4[2]))


def vector3_to_vector4(v3):
    return Vector((v3[0], v3[1], v3[2], 0))


class MetaBone():
    """ A MetaBone object stores common values between pchans, ebones, and metabones, and helps control how information is copied between them """
    ebone_attrs = {'head': Vector((0, 0, 0)),
                   'tail': Vector((0, 1, 0)),
                   'roll': 0,
                   'tail_radius': None,
                   'head_radius': None,
                   'bbone_x': None,
                   'bbone_z': None,
                   'bbone_in': 0,
                   'bbone_out': 0,
                   'bbone_segments': 1,
                   'use_connect': False,
                   'use_deform': False,
                   'use_envelope_multiply': False,
                   'use_inherit_rotation': True,
                   'envelope_distance': None}

    pchan_attrs = {'use_bepuik': False,
                   'use_bepuik_always_solve': False,
                   'bepuik_ball_socket_rigidity': 0,
                   'bepuik_rotational_heaviness': 2.5,
                   'lock_location': (False, False, False),
                   'lock_rotation': (False, False, False),
                   'lock_rotation_w': False,
                   'lock_rotations_4d': False,
                   'lock_scale': (False, False, False),
                   'custom_shape': None,
                   'rotation_mode': 'QUATERNION'}

    #can only be accessed thru the bone context for some strange reason
    bone_attrs = {'show_wire': False}

    special_attrs = {'align_roll': Vector((0, 0, 1)),
                     'parent': None}

    all_attrs = dict(list(ebone_attrs.items()) +
                     list(pchan_attrs.items()) +
                     list(bone_attrs.items()) +
                     list(special_attrs.items()))

    def __init__(self, name, metabone=None, transform=None, length=None):
        self.meta_blender_constraints = []

        if metabone:
            for attr in MetaBone.all_attrs.keys():
                safesetattr(self, attr, getattr(metabone, attr))
        else:
            for attr, val in MetaBone.all_attrs.items():
                safesetattr(self, attr, val)

        if transform:
            self.head = transform * self.head
            self.tail = transform * self.tail
            self.align_roll = transform.to_3x3() * self.align_roll

            if length:
                self.tail = self.head + (self.y_axis() * length)

        self.name = name

    def copy_pchan_data(self, pchan):
        for attr in MetaBone.pchan_attrs.keys():
            safesetattr(self, attr, getattr(pchan, attr))

        for attr in MetaBone.bone_attrs.keys():
            safesetattr(self, attr, getattr(pchan.bone, attr))

    def copy_ebone_data(self, ebone):
        for attr in MetaBone.ebone_attrs.keys():
            safesetattr(self, attr, getattr(ebone, attr))

        self.align_roll = ebone.z_axis.copy()

    def is_valid(self):
        return self.length() > 0.0001

    def create_ebone(self, ob):
        if not self.is_valid():
            return None

        length = (self.tail - self.head).length
        ebone = ob.data.edit_bones.new(name=self.name)

        if not self.head_radius:
            self.head_radius = length / 10

        if not self.tail_radius:
            self.tail_radius = length / 10

        if not self.bbone_x:
            self.bbone_x = length / 10

        if not self.bbone_z:
            self.bbone_z = length / 10

        if not self.envelope_distance:
            self.envelope_distance = self.head_radius * 15

        for attr in MetaBone.ebone_attrs.keys():
            val = getattr(self, attr)
            safesetattr(ebone, attr, val)

        ebone.align_roll(self.align_roll.normalized())

        #create editbone selects the tail, but we dont want that
        ebone.select_tail = False

        return ebone

    def apply_data_to_pchan(self, pchan):
        for attr in MetaBone.pchan_attrs.keys():
            safesetattr(pchan, attr, getattr(self, attr))

        for attr in MetaBone.bone_attrs.keys():
            safesetattr(pchan.bone, attr, getattr(self, attr))

    def apply_data_to_pchan_constraints(self, pchan):
        for meta_blender_constraint in self.meta_blender_constraints:
            if meta_blender_constraint.name in pchan.constraints:
                continue

            meta_blender_constraint.apply_data_to_pchan(pchan)

    def new_meta_blender_constraint(self, type, targetmetabone=None, name=None):
        """

        :arg type: type of blender constraint
        :type type: str
        :arg targetmetabone: other bone being targed by this constraint
        :type targetmetabone: MetaBone
        :arg name: name of new meta blender constraint, which will be applied to the final blender constraint
        :type name: str
        :return: a new MetaBlenderConstraint
        :rtype: MetaBlenderConstraint
        """
        if not name:
            name = "%s %s" % (type.lower().replace("_", " "), len(self.meta_blender_constraints) + 1)

        mbc = MetaBlenderConstraint(type, name)

        mbc.connection_a = self
        if targetmetabone:
            mbc.connection_b = targetmetabone

        self.meta_blender_constraints.append(mbc)
        return mbc

    @classmethod
    def from_ebone(cls, ebone):
        metabone = cls(name=ebone.name)

        metabone.copy_ebone_data(ebone)

        return metabone

    def y_axis(self):
        v = (self.tail - self.head)
        assert not vector_is_zero(v), "%s has same tail and head" % self.name
        return v.normalized()

    def x_axis(self):
        y = self.y_axis()
        ar = self.align_roll

        c = y.cross(ar)
        if vector_is_zero(c):
            c = y.cross(Vector((ar[0], -ar[2], ar[1])))

        return c.normalized()

    def z_axis(self):
        return self.x_axis().cross(self.y_axis()).normalized()

    def center(self):
        return (self.head + self.tail) / 2

    def matrix(self):
        m = Matrix.Identity(4)

        m.col[0] = vector3_to_vector4(self.x_axis())
        m.col[1] = vector3_to_vector4(self.y_axis())
        m.col[2] = vector3_to_vector4(self.z_axis())
        m.col[3] = vector3_to_vector4(self.head)
        m.col[3][3] = 1.0

        m.normalize()

        return m

    def length(self):
        return (self.tail - self.head).length


def suffixed(name, suffixletter):
    if suffixletter:
        return "%s.%s" % (name, suffixletter)
    else:
        return name


class MetaBoneDict(dict):
    def __init__(self, *args):
        dict.__init__(self, args)

    def __getitem__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        else:
            return None

    def __setitem__(self, key, val):
        if key in self:
            raise Exception("Cannot add metabone with name %s! Already exists!" % key)
        dict.__setitem__(self, key, val)

    def new_bone(self, name, metabone=None, transform=None, length=None):
        self[name] = MetaBone(name, metabone, transform, length)
        return self[name]

    def new_bone_by_fraction(self, name, source_metabone, start_fraction=0, end_fraction=1):
        new_bone = self.new_bone(name=name)
        new_bone.name = name
        start_point = source_metabone.head
        end_point = source_metabone.tail

        local_vector = (end_point - start_point)
        local_start = local_vector * start_fraction
        local_end = local_vector * end_fraction
        new_bone.head = start_point + local_start
        new_bone.tail = start_point + local_end

        new_bone.align_roll = source_metabone.align_roll
        new_bone.bbone_x = source_metabone.bbone_x
        new_bone.bbone_z = source_metabone.bbone_z
        return new_bone

    @classmethod
    def from_bakedata(cls, bakedata_list):
        destination_metabones = cls()

        for bake in bakedata_list:
            for source_name, source_metabone in bake.metabones.items():
                destination_metabones.new_bone(suffixed(source_name, bake.suffixletter), source_metabone,
                                               bake.transform)

        #the destination_metabone.parent attribute still point to metabones in the source metabone group, so 
        #we need to update them to be pointing to the metabones in the destination group         
        for bake in bakedata_list:
            for source_name, source_metabone in bake.metabones.items():
                destination_metabone = destination_metabones[suffixed(source_name, bake.suffixletter)]

                if destination_metabone.parent:
                    destination_metabone.parent = destination_metabones[
                        suffixed(destination_metabone.parent.name, bake.suffixletter)]

        return destination_metabones


    @classmethod
    def from_transform_length_pairs(cls, name, transform_length_pairs):
        metabones = cls()

        num_id = 1
        prev_bone = None
        t = Matrix.Identity(4)
        for transform, length in transform_length_pairs:
            t = t * transform
            new_bone = metabones.new_bone("%s-%s" % (name, num_id))
            new_bone.head = vector4_to_vector3(t.col[3])
            new_bone.align_roll = vector4_to_vector3(t.col[2])
            t = t * Matrix.Translation(Vector((0, length, 0)))
            new_bone.tail = vector4_to_vector3(t.col[3])

            if prev_bone:
                new_bone.parent = prev_bone

                if (prev_bone.tail - new_bone.head).length < .0001:
                    new_bone.use_connect = True
                else:
                    new_bone.use_connect = False
            else:
                new_bone.use_connect = False

            prev_bone = new_bone

            num_id += 1

        return metabones

    @classmethod
    def from_angle_length_pairs(cls, name, angle_length_pairs):
        transform_length_pairs = []

        for angle, length in angle_length_pairs:
            transform_length_pairs.append((Matrix.Rotation(angle, 4, 'X'), length))

        return cls.from_transform_length_pairs(name, transform_length_pairs)


    @classmethod
    def from_ob(cls, ob):
        assert ob.type == 'ARMATURE'
        assert ob.mode == 'POSE'
        assert ob == bpy.context.object

        metabones = MetaBoneDict()

        for pchan in ob.pose.bones:
            metabone = metabones.new_bone(pchan.name)
            metabone.copy_pchan_data(pchan)

        bpy.ops.object.mode_set(mode='EDIT', toggle=False)

        for name, metabone in metabones.items():
            ebone = ob.data.edit_bones[name]
            metabone.copy_ebone_data(ebone)

            if ebone.parent:
                metabones[ebone.name].parent = metabones[ebone.parent.name]

        return metabones

    def to_ob(self, ob):
        assert bpy.context.object == ob
        assert ob.type == 'ARMATURE'
        assert ob.mode == 'EDIT'

        ebone_creators = []

        for metabone in self.values():
            if metabone.name not in ob.data.edit_bones:
                if metabone.create_ebone(ob):
                    ebone_creators.append(metabone)

        for metabone in ebone_creators:
            ebone = ob.data.edit_bones[metabone.name]
            if metabone.parent and metabone.parent.is_valid():
                ebone.parent = ob.data.edit_bones[metabone.parent.name]

        bpy.ops.object.mode_set(mode='POSE')

        for metabone in ebone_creators:
            pchan = ob.pose.bones[metabone.name]
            metabone.apply_data_to_pchan(pchan)

        for metabone in self.values():
            if metabone.is_valid():
                pchan = ob.pose.bones[metabone.name]
                metabone.apply_data_to_pchan_constraints(pchan)

    def get_args_subset(self, local_names, suffixletter):
        arm_metabones = {}
        for local_name in local_names:
            name = "%s.%s" % (local_name, suffixletter)
            if name not in self:
                name = local_name

            assert name in self, "%s couldn't be found in metabones!" % name

            arm_metabones[local_name] = self[name]
        return arm_metabones


class MetaBonesBakeData():
    def __init__(self, metabones, transform=None, suffixletter=""):
        self.metabones = metabones
        self.suffixletter = suffixletter
        self.transform = transform


def translation4(vec):
    return Matrix.Translation(vec).to_4x4()


def metabones_get_phalange_segment(mbs, name, phalange_num, segment_num, suffixletter):
    return mbs["%s%s-%s.%s" % (name, phalange_num, segment_num, suffixletter)]


def metabones_get_segment_siblings(mbs, name, s, suffixletter, max_num_phalange=5):
    segment_siblings = []
    for p in range(1, max_num_phalange + 1):
        segment = metabones_get_phalange_segment(mbs, name, p, s, suffixletter)
        if segment:
            segment_siblings.append(segment)

    return segment_siblings


def metabones_add_hand(mbs, suffixletter, proximal_bones, use_thumb):
    hand_name = "hand.%s" % suffixletter
    hand = mbs[hand_name]
    assert not hand
    loarm = mbs["loarm.%s" % suffixletter]
    assert loarm

    hand = mbs.new_bone("hand.%s" % suffixletter)
    hand.parent = loarm
    hand.head = loarm.tail.copy()
    hand.tail = sum_vectors([proximal.head for proximal in proximal_bones]) / len(proximal_bones)
    hand.use_connect = True

    if use_thumb and len(proximal_bones) > 1:
        aligner_bones = proximal_bones[1:]
    else:
        aligner_bones = proximal_bones

    hand.align_roll = sum_vectors([p.align_roll for p in aligner_bones]) / len(aligner_bones)

    return hand


def metabones_count_num_fingers(mbs, suffix):
    p = re.compile(r"finger[0-9]+-")
    matched_finger_prefixes = set()
    for mbname, mb in mbs:
        if mbname.endswith(suffix):
            match = p.match(mbname)
            if match:
                matched_finger_prefixes.add(match.group(0))

    return len(matched_finger_prefixes)

def meta_create_full_body(ob, num_fingers, num_toes, foot_width, wrist_width, wrist_yaw, wrist_pitch, wrist_roll,
                          use_thumb, finger_curl, toe_curl, finger_splay, thumb_splay, thumb_tilt, arm_yaw,
                          arm_pitch, arm_roll, shoulder_head_vec,
                          shoulder_tail_vec, elbow_vec, wrist_vec, spine_start_vec, spine_pitch, spine_lengths,
                          upleg_vec, knee_vec,
                          ankle_vec, toe_vec, head_length, head_pitch, eye_center, eye_radius, chin_vec, jaw_vec,
                          use_simple_toe, num_tail_bones, tail_length, use_ears, use_belly, use_bepuik_tail, use_simple_hand):
    spine_meta = meta_init_spine(spine_lengths, use_belly, num_tail_bones, tail_length)
    spine_mat = translation4(spine_start_vec) * Matrix.Rotation(spine_pitch, 4, 'X')

    shoulder_meta = meta_init_shoulder(shoulder_tail_vec)
    shoulder_mat = spine_mat * translation4(shoulder_head_vec)

    arm_meta = meta_init_uparm_loarm(shoulder_meta["shoulder"], elbow_vec, wrist_vec)
    arm_mat = shoulder_mat * \
              translation4(shoulder_meta["shoulder"].tail) * \
              Matrix.Rotation(arm_yaw, 4, 'Z') * \
              Matrix.Rotation(arm_pitch, 4, 'X') * \
              Matrix.Rotation(arm_roll, 4, 'Y')

    fingers_meta = meta_init_fingers(num_fingers, finger_curl, wrist_width, use_thumb, finger_splay, thumb_splay,
                                     thumb_tilt)
    fingers_mat = arm_mat * \
                  translation4(arm_meta["loarm"].tail) * \
                  Matrix.Rotation(wrist_yaw, 4, 'Z') * \
                  Matrix.Rotation(wrist_pitch, 4, 'X') * \
                  Matrix.Rotation(wrist_roll, 4, 'Y')

    leg_meta = meta_init_leg(upleg_vec, knee_vec, ankle_vec, toe_vec, foot_width)
    leg_mat = Matrix.Identity(4)

    toes_meta = meta_init_toes(num_toes, toe_curl, foot_width, use_simple_toe)
    toes_mat = leg_mat * translation4(leg_meta["foot"].tail) * Matrix.Rotation(math.pi, 4, 'Z')

    head_meta = meta_init_head(spine_meta["neck"], head_length, eye_center, eye_radius, chin_vec, jaw_vec, use_ears)
    head_mat = spine_mat * translation4(spine_meta["neck"].tail) * Matrix.Rotation(head_pitch, 4, 'X')

    flip = Matrix.Scale(-1, 4, Vector((1, 0, 0)))

    bakedata_list = [MetaBonesBakeData(spine_meta, spine_mat), MetaBonesBakeData(head_meta, head_mat)]


    for mat, suffixletter in (Matrix.Identity(4), "L"), (flip, "R"):
        side = [MetaBonesBakeData(shoulder_meta, mat * shoulder_mat, suffixletter),
                MetaBonesBakeData(arm_meta, mat * arm_mat, suffixletter),
                MetaBonesBakeData(fingers_meta, mat * fingers_mat, suffixletter),
                MetaBonesBakeData(leg_meta, mat * leg_mat, suffixletter),
                MetaBonesBakeData(toes_meta, mat * toes_mat, suffixletter)]
        bakedata_list.extend(side)

    #    testleft = MetaBoneDict()
    #    b = testleft.new_bone("test")
    #    b.head = Vector((0,0,0))
    #    b.tail = Vector((1,0,0))
    #
    #    bakedata_list.append(MetaBonesBakeData(testleft,Matrix.Identity(4) * mat_fingers,'L'))
    #    bakedata_list.append(MetaBonesBakeData(testleft,flip * mat_fingers,'R'))

    combined_metabones = MetaBoneDict.from_bakedata(bakedata_list)

    if use_simple_hand:
        for suffixletter in ("L", "R"):
            proximal_bones = []
            for i in range(num_fingers):
                palm_bone = metabones_get_phalange_segment(combined_metabones, "finger", i+1, 1, suffixletter)

                if palm_bone:
                    combined_metabones.pop(palm_bone.name)

                proximal = metabones_get_phalange_segment(combined_metabones, "finger", i+1, 2, suffixletter)
                if proximal:
                    proximal.parent = None
                    proximal.use_connect = False
                    proximal_bones.append(proximal)

            metabones_add_hand(combined_metabones, suffixletter, proximal_bones, use_thumb)

    combined_metabones.to_ob(ob)

    ob.data.layers = [True] * 32
    ob.bepuik_autorig.is_meta_armature = True
    ob.bepuik_autorig.use_thumb = use_thumb
    ob.bepuik_autorig.use_simple_toe = use_simple_toe
    ob.bepuik_autorig.use_bepuik_tail = use_bepuik_tail
    ob.bepuik_autorig.use_simple_hand = use_simple_hand


def meta_init_faceside(eye_center, eye_radius, use_ears, jaw_vec, head_length):
    metabones = MetaBoneDict()

    b = metabones.new_bone("eye")
    b.head = eye_center.copy()
    b.tail = eye_center + Vector((0, -1 * eye_radius, 0))

    if use_ears:
        b = metabones.new_bone("ear")
        b.head = Vector((eye_center[0], jaw_vec[1], eye_center[2]))
        b.tail = b.head + (Vector((0,0,1)) * (head_length/2))
        b.use_deform = True
        b.lock_location = (True, True, True)
        b.align_roll = Vector((0,-1,0))

    return metabones


def meta_init_head(neck, head_length, eye_center, eye_radius, chin_vec, jaw_vec, use_ears):
    face_side_meta = meta_init_faceside(eye_center, eye_radius, use_ears, jaw_vec, head_length)

    bakedata_list = [MetaBonesBakeData(face_side_meta, Matrix.Identity(4), 'L'),
                     MetaBonesBakeData(face_side_meta, Matrix.Scale(-1, 4, Vector((1, 0, 0))), 'R')]
    combined_metabones = MetaBoneDict.from_bakedata(bakedata_list)

    head = combined_metabones.new_bone('head')
    head.head = Vector((0, 0, 0))
    head.tail = Vector((0, 0, head_length))
    head.align_roll = Vector((0,-1,0))
    head.use_connect = True
    head.parent = neck

    jaw = combined_metabones.new_bone('jaw')
    jaw.head = jaw_vec.copy()
    jaw.tail = chin_vec.copy()
    jaw.use_connect = False
    jaw.parent = head

    return combined_metabones


def meta_init_spine(spine_lengths, use_belly, num_tail_bones, tail_length):
    mbg = MetaBoneDict()

    bone_names = ["hips", "spine", "chest", "neck"]

    v = Vector((0, 0, 0))

    def get_prev_bone_by_spine_length_index(i):
        if i - 1 >= 0:
            return mbg[bone_names[i - 1]]

        return None

    for spine_length_index in range(len(spine_lengths)):
        new_bone = mbg.new_bone(bone_names[spine_length_index])
        new_bone.head = v.copy()
        v += Vector((0, 0, spine_lengths[spine_length_index]))
        new_bone.tail = v.copy()
        new_bone.align_roll = Vector((0, -1, 0))
        new_bone.parent = get_prev_bone_by_spine_length_index(spine_length_index)
        if new_bone.parent:
            new_bone.use_connect = True

    chest_length = (mbg["chest"].tail - mbg["chest"].head).length
    rib_head_z = mbg["chest"].head[2] + (chest_length * .2)
    rib_tail_z = mbg["chest"].tail[2] - (chest_length * .4)

    b = mbg.new_bone("ribs.L")
    b.head = Vector((0.074, -0.086, rib_head_z))
    b.tail = Vector((0.102, -0.024, rib_tail_z))
    b.align_roll = Vector((0, -1, 0))
    b.parent = mbg["chest"]

    b = mbg.new_bone("ribs.R")
    b.head = Vector((-0.074, -0.086, rib_head_z))
    b.tail = Vector((-0.102, -0.024, rib_tail_z))
    b.align_roll = Vector((0, -1, 0))
    b.parent = mbg["chest"]

    if use_belly:
        spine = mbg["spine"]
        belly = mbg.new_bone("belly")
        belly.head = ((spine.head+spine.tail)/2) + (spine.align_roll * (spine.length()/3))
        belly.tail = belly.head + (spine.align_roll * (spine.length()))
        belly.align_roll = spine.y_axis()
        belly.parent = spine
        belly.use_deform = True

    if num_tail_bones > 0:
        spine = mbg["spine"]
        hips = mbg["hips"]

        length_per_segment = tail_length/num_tail_bones

        tail_direction = -spine.align_roll
        tail_segment_offset = tail_direction * length_per_segment
        tposition = spine.head + (tail_direction * (spine.length()/2))

        parent = hips
        for i in range(num_tail_bones):
            tail = mbg.new_bone("tail%s" % (i+1))
            tail.head = tposition.copy()

            tposition += tail_segment_offset
            tail.tail = tposition.copy()

            tail.align_roll = spine.y_axis()
            tail.use_deform = True
            tail.parent = parent
            tail.bbone_segments = 4
            tail.bbone_in = 1
            tail.bbone_out = 1

            if parent != hips:
                tail.use_connect = True
            else:
                tail.inherit_rotation = False


            parent = tail
        tail.use_bepuik_always_solve = True

    return mbg


def meta_init_shoulder(shoulder_tail_vec):
    mbg = MetaBoneDict()

    shoulder = mbg.new_bone("shoulder")
    shoulder.use_deform = True
    shoulder.head = Vector((0, 0, 0))
    shoulder.tail = shoulder_tail_vec.copy()
    shoulder.use_bepuik_ball_socket_rigidity = BEPUIK_BALL_SOCKET_RIGIDITY_DEFAULT

    return mbg


def meta_init_uparm_loarm(shoulder, elbow_vec, wrist_vec):
    mbg = MetaBoneDict()

    uparm = mbg.new_bone("uparm")
    uparm.head = Vector((0, 0, 0))
    uparm.tail = Vector((elbow_vec[0], elbow_vec[1], 0))
    uparm.use_connect = True
    uparm.parent = shoulder

    loarm = mbg.new_bone("loarm")
    loarm.head = uparm.tail.copy()
    loarm.tail = Vector((wrist_vec[0], wrist_vec[1], 0))
    loarm.parent = uparm
    loarm.use_connect = True

    return mbg


class Phalange():
    def __init__(self, name, curl, lengths, length_scale):
        self.name = name
        self.curl = curl
        self.lengths = lengths
        self.lengths_scale = length_scale

    def create_metabonedict(self):
        angle_length_pairs = [(0, self.lengths[0] * self.lengths_scale)]
        for i in range(1, len(self.lengths)):
            angle_length_pairs.append((self.curl, self.lengths[i] * self.lengths_scale))

        return MetaBoneDict.from_angle_length_pairs(self.name, angle_length_pairs)


class Finger(Phalange):
    def __init__(self, name, curl, lengths, length_scale, is_thumb=False):
        super().__init__(name, curl, lengths, length_scale)
        self.is_thumb = is_thumb


class Toe(Phalange):
    def __init__(self, name, curl, lengths, length_scale):
        super().__init__(name, curl, lengths, length_scale)


def meta_init_fingers(num_fingers, finger_curl, wrist_width, use_thumb, finger_splay, thumb_splay, thumb_tilt):
    thumb_segment_lengths = [.024, .0376, .040, .0339]
    finger_segment_lengths = [.089, .0318, .02632, .0247]

    #from thumb to pinky
    finger_scales = [.7, .9, 1, .9, .7]

    fingers = []

    if use_thumb:
        segment_lengths = thumb_segment_lengths
    else:
        segment_lengths = finger_segment_lengths

    fingers.append(Finger("finger1", finger_curl, segment_lengths, finger_scales[0], use_thumb))

    for finger_index in range(1, num_fingers):
        fingers.append(
            Finger("finger%s" % (finger_index + 1), finger_curl, finger_segment_lengths, finger_scales[finger_index]))

    fingers_bakedata = []

    if num_fingers > 1:
        wrist_point = Vector((wrist_width / 2, 0, 0))
        wrist_delta = wrist_width / (num_fingers - 1)
    else:
        wrist_width = 0
        wrist_delta = 0
        wrist_point = Vector((0, 0, 0))

    for finger in fingers:
        metabones = finger.create_metabonedict()

        if wrist_width > 0:
            wrist_factor = wrist_point[0] / wrist_width / 2
        else:
            wrist_factor = wrist_point[0]

        if finger.is_thumb:
            transform = Matrix.Translation(wrist_point) * Matrix.Rotation(math.radians(90), 4, 'Y') * Matrix.Rotation(
                thumb_splay, 4, 'X') * Matrix.Rotation(thumb_tilt, 4, 'Z')
        else:
            transform = Matrix.Translation(wrist_point) * Matrix.Rotation(wrist_factor * finger_splay, 4, 'Z')

        fingers_bakedata.append(MetaBonesBakeData(metabones, transform))
        wrist_point[0] -= wrist_delta

    return MetaBoneDict.from_bakedata(fingers_bakedata)


def meta_init_toes(num_toes, toe_curl, foot_width, use_simple_toe=True):
    big_toe_lengths = [.02955, .02653]
    little_toe_lengths = [.028, .01628, .015]

    if use_simple_toe:
        big_toe_lengths = [sum(big_toe_lengths), ]
        little_toe_lengths = [sum(little_toe_lengths), ]

    #from bigtoe to pinky toe
    toe_scales = []
    scale = 1
    for i in range(num_toes):
        toe_scales.append(scale)
        scale *= .80

    toes = [Toe("toe1", toe_curl, big_toe_lengths, toe_scales[0])]

    for toe_index in range(1, num_toes):
        toes.append(Toe("toe%s" % (toe_index + 1), toe_curl, little_toe_lengths, toe_scales[toe_index]))

    toes_bakedata = []

    if num_toes > 1:
        foot_point = Vector((foot_width / 2, 0, 0))
        foot_delta = foot_width / (num_toes - 1)
    else:
        foot_delta = 0
        foot_point = Vector((0, 0, 0))

    for toe in toes:
        metabones = toe.create_metabonedict()

        transform = Matrix.Translation(foot_point)

        toes_bakedata.append(MetaBonesBakeData(metabones, transform))
        foot_point[0] -= foot_delta

    return MetaBoneDict.from_bakedata(toes_bakedata)


def meta_init_leg(upleg_vec, knee_vec, ankle_vec, toe_vec, foot_width):
    mbg = MetaBoneDict()

    upleg = mbg.new_bone("upleg")
    upleg.use_deform = True
    upleg.head = upleg_vec.copy()
    upleg.tail = knee_vec.copy()
    upleg.align_roll = Vector((0, -1, 0))

    loleg = mbg.new_bone("loleg")
    loleg.head = upleg.tail.copy()
    loleg.tail = ankle_vec.copy()
    loleg.parent = upleg
    loleg.align_roll = Vector((0, -1, 0))
    loleg.use_connect = True

    foot = mbg.new_bone("foot")
    foot.head = loleg.tail.copy()
    foot.tail = toe_vec.copy()
    foot.parent = loleg
    foot.bepuik_ball_socket_rigidity = 1000
    foot.use_connect = True

    heel_floor_pos = geometry.intersect_line_plane(loleg.head, loleg.tail, Vector((0, 0, 0)), Vector((0, 0, 1)))

    if heel_floor_pos is None:
        heel_floor_pos = loleg.tail + (loleg.y_axis() * (foot.length()/2))

    heel_width_axis = Vector((-foot.y_axis()[1], foot.y_axis()[0], 0)).normalized()
    offest_dir_from_center_of_heel = heel_width_axis * foot_width / 2

    heel_bone = mbg.new_bone("heel")
    heel_bone.head = heel_floor_pos - offest_dir_from_center_of_heel
    heel_bone.tail = heel_floor_pos + offest_dir_from_center_of_heel

    return mbg


def degrees_between(a, b):
    if type(a) == MetaBone:
        a = a.y_axis()

    if type(b) == MetaBone:
        b = b.y_axis()

    return math.degrees(a.angle(b))


def rig_target_affected(target, affected, headtotail=0, position_rigidity=0, orientation_rigidity=0,
                        hard_rigidity=False, use_rest_offset=False):
    name, side_suffix = split_suffix(target.name)
    if name.endswith(" target"):
        name = name[:-len(" target")]

    metaconstraint = affected.new_meta_blender_constraint('BEPUIK_CONTROL', target,
                                                          "%s control%s" % (name, side_suffix))
    metaconstraint.connection_b = target
    metaconstraint.orientation_rigidity = orientation_rigidity
    metaconstraint.bepuik_rigidity = position_rigidity
    metaconstraint.use_hard_rigidity = hard_rigidity
    metaconstraint.pulled_point = (0, headtotail, 0)
    metaconstraint.use_rest_offset = use_rest_offset
    target.show_wire = True
    target.lock_scale = (True, True, True)

    return metaconstraint


def rig_twist_limit(a, b, twist):
    """
    create a twist limit with metabone b as the basis for everything

    :param a: a target
    :param b: b target
    :param twist: twist amount
    :return: twist limit meta blender constraint
    """
    c = a.new_meta_blender_constraint('BEPUIK_TWIST_LIMIT', b)
    c.axis_a = b, 'Y'
    c.axis_b = b, 'Y'
    c.measurement_axis_a = b, 'Z'
    c.measurement_axis_b = b, 'Z'
    c.max_twist = twist

    return c


def rig_swing_limit(a, b, swing):
    c = a.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', b)
    c.axis_a = b, 'Y'
    c.axis_b = b, 'Y'

    c.max_swing = swing


def sum_vectors(vecs):
    v_sum = Vector((0, 0, 0))
    for v in vecs:
        v_sum += v

    return v_sum


def rig_full_body(meta_armature_obj, op=None):
    custom_widget_data = {}

    printmsgs = []

    def widget_get(name):
        return widgetdata_get(name, custom_widget_data)

    bpy.ops.object.mode_set(mode='POSE')
    mbs = MetaBoneDict.from_ob(meta_armature_obj)

    eyel = mbs["eye.L"]
    eyer = mbs["eye.R"]
    jaw = mbs["jaw"]
    hips = mbs["hips"]
    head = mbs["head"]
    chest = mbs["chest"]
    spine = mbs["spine"]
    neck = mbs["neck"]
    ribsl = mbs["ribs.L"]
    ribsr = mbs["ribs.R"]
    legl = mbs["upleg.L"]
    legr = mbs["upleg.R"]
    shoulderl = mbs["shoulder.L"]
    shoulderr = mbs["shoulder.R"]

    bpy.ops.object.mode_set(mode='OBJECT')
    meta_armature_obj.select = False
    meta_armature_obj.hide = True

    rig_ob = bpy.data.objects.new('Rig', bpy.data.armatures.new("Rig Bones"))
    bpy.context.scene.objects.link(rig_ob)
    bpy.context.scene.objects.active = rig_ob
    rig_ob.select = True

    root = mbs.new_bone("root")
    root.head = Vector((0, 0, 0))
    root.tail = Vector((0, 1, 0))
    root.align_roll = Vector((0, 0, 1))
    root.custom_shape = widget_get(WIDGET_ROOT)
    root.show_wire = True

    if eyel and eyer:
        avg_eye_length = (eyel.length() + eyer.length()) / 2
        avg_eye_tail_loc = (eyel.tail + eyer.tail) / 2
        eye_target_head = Vector((0, avg_eye_tail_loc[1] - .5, avg_eye_tail_loc[2]))
    elif eyel:
        avg_eye_length = eyel.length()
        eye_target_head = Vector((0, eyel.tail[1] - .5, eyel.tail[2]))
    elif eyer:
        avg_eye_length = eyer.length()
        eye_target_head = Vector((0, eyer.tail[1] - .5, eyer.tail[2]))

    if eyel or eyer:
        eye_target = mbs.new_bone('eye target')
        eye_target.head = eye_target_head
        eye_target.tail = eye_target.head + Vector((0, -(avg_eye_length*2), 0))
        eye_target.custom_shape = widget_get(WIDGET_EYE_TARGET)
        eye_target.parent = root
        eye_target.show_wire = True

    if jaw:
        jaw.use_deform = True
        jaw.lock_location = (True, True, True)
        jaw.parent = head

    def rig_rib(rib):
        rib.parent = chest
        rib.use_deform = True

    def spine_defaults(bone_list):
        prev_bone = None
        for bone in bone_list:
            bone.use_deform = True
            bone.use_bepuik = True

            if prev_bone:
                bone.use_connect = True
                bone.bepuik_ball_socket_rigidity = BEPUIK_BALL_SOCKET_RIGIDITY_DEFAULT
                bone.parent = prev_bone

            prev_bone = bone

    rig_rib(ribsl)
    rig_rib(ribsr)

    spine_defaults([hips, spine, chest, neck, head])
    chest.use_bepuik_always_solve = True

    head.bepuik_rotational_heaviness = 30

    neck.bbone_in = .7
    neck.bbone_out = 1
    neck.bbone_segments = 7
    neck.bepuik_rotational_heaviness = 10

    hips.bepuik_rotational_heaviness = 12

    spine.bbone_segments = 8
    spine.bbone_in = 1
    spine.bbone_out = 1
    spine.bepuik_rotational_heaviness = 14

    rig_twist_limit(hips, chest, twist=45)

    rig_swing_limit(hips, spine, 60)
    rig_swing_limit(spine, chest, 60)
    rig_swing_limit(chest, neck, 60)

    rig_twist_joint(hips, spine)
    rig_twist_joint(chest, neck)

    tail_bones = []
    for i in range(20):
        name = "tail%s" % (i+1)
        if name in mbs:
            tail_bones.append(mbs[name])

    if len(tail_bones) > 0:
        if meta_armature_obj.bepuik_autorig.use_bepuik_tail:
            prev_tail_bone = None
            for t in range(len(tail_bones)):
                flag_bone_deforming_ballsocket_bepuik(tail_bones[t])
                if prev_tail_bone:
                    rig_twist_limit(prev_tail_bone, tail_bones[t], twist=30)
                rig_new_target(mbs, "tail%s target" % (t+1), tail_bones[t], root, headtotail=1)
                prev_tail_bone = tail_bones[t]
        else:
            tail_bones[0].lock_location = (True, True, True)

    #spine stiffness stuff
    chest_stiffness = mbs.new_bone("chest stiff")
    chest_stiffness.head = chest.head.copy()
    chest_stiffness.tail = chest.tail.copy()
    chest_stiffness.custom_shape = widget_get(WIDGET_STIFF_TRIANGLE)
    chest_stiffness.parent = spine
    chest_stiffness.show_wire = True
    chest_stiffness.use_connect = False #cannot use connect or else the bbone for the spine wont work
    chest_stiffness.align_roll = chest.align_roll.copy()
    chest_stiffness.lock_location = (True,True,True)

    spine_stiffness = mbs.new_bone("spine stiff")
    spine_stiffness.head = spine.head.copy()
    spine_stiffness.tail = spine.tail.copy()
    spine_stiffness.custom_shape = widget_get(WIDGET_STIFF_CIRCLE)
    spine_stiffness.parent = hips
    spine_stiffness.show_wire = True
    spine_stiffness.use_connect = True
    spine_stiffness.align_roll = spine.align_roll.copy()
    spine_stiffness.rotation_mode = 'YZX'
    spine_stiffness.lock_rotation = (False, True, False)

    spine_stiff_angular_joint = hips.new_meta_blender_constraint('BEPUIK_ANGULAR_JOINT', spine)
    spine_stiff_angular_joint.relative_orientation = spine_stiffness
    spine_stiff_angular_joint.use_rest_offset = True
    spine_stiff_angular_joint.bepuik_rigidity = 1.0

    chest_stiff_angular_joint = spine.new_meta_blender_constraint('BEPUIK_ANGULAR_JOINT', chest)
    chest_stiff_angular_joint.relative_orientation = chest_stiffness
    chest_stiff_angular_joint.use_rest_offset = True
    chest_stiff_angular_joint.bepuik_rigidity = 1.0

    hips.parent = root

    hips_target = rig_new_target(mbs, "hips target", hips, root)
    chest_target = rig_new_target(mbs, "chest target", chest, root)
    rig_new_target(mbs, "spine target", spine, root)
    rig_new_target(mbs, "head target", head, root)

    def replace_target_widget_with_circle_widget(width_world, target):
        #replace default hips_target widget with new hips circle widget

        width_local = width_world / target.length()

        wd = custom_widget_data["widget %s" % target.name] = widgetdata_circle(width_local/2)
        wd.edges.append((12, 28))

        target.custom_shape = widget_get("widget %s" % target.name)
        #end create hips circle widget

    if legl and legr:
        width = (legr.head - legl.head).length
    else:
        width = .25
    replace_target_widget_with_circle_widget(width, hips_target)

    if shoulderl and shoulderr:
        width = (shoulderl.tail - shoulderr.tail).length * .85
    else:
        width = .3
    replace_target_widget_with_circle_widget(width, chest_target)

    hips_down_mat = hips.matrix() * Matrix.Rotation(math.pi, 4, 'Z')
    hips_forward_mat = hips_down_mat * Matrix.Rotation(math.pi / 2, 4, 'X')

    up = Vector((0, 0, 1))
    forward = Vector((0, -1, 0))

    def rig_side(suffixletter):
        if suffixletter == "L":
            relative_x_axis = 'X'
            leg_relative_x_axis = 'NEGATIVE_X'
            measurement_axis_mat = hips_forward_mat * Matrix.Rotation(math.pi / 5, 4, 'Z')
        else:
            relative_x_axis = 'NEGATIVE_X'
            leg_relative_x_axis = 'X'
            measurement_axis_mat = hips_forward_mat * Matrix.Rotation(-math.pi / 5, 4, 'Z')

        loleg = mbs["loleg.%s" % suffixletter]
        upleg = mbs["upleg.%s" % suffixletter]
        foot = mbs["foot.%s" % suffixletter]
        eye = mbs["eye.%s" % suffixletter]
        ear = mbs["ear.%s" % suffixletter]
        shoulder = mbs["shoulder.%s" % suffixletter]
        uparm = mbs["uparm.%s" % suffixletter]
        loarm = mbs["loarm.%s" % suffixletter]
        heel_bone = mbs["heel.%s" % suffixletter]

        def get_phalange_segment(name, p, s):
            return mbs["%s%s-%s.%s" % (name, p, s, suffixletter)]

        def create_phalange_swingcenter(name, p, s):
            return mbs.new_bone("MCH-%s%s %s swingcenter.%s" % (name, p, s, suffixletter))

        def get_final_segments(name):
            final_segments = []
            for p in range(1, 6):
                for s in [3, 2, 1]:
                    segment = get_phalange_segment(name, p, s)
                    if segment:
                        final_segments.append(segment)
                        break

            return final_segments

        def rig_hand():
            def get_finger_segment(f, s):
                return get_phalange_segment("finger", f, s)

            def create_finger_swingcenter(f, s):
                return create_phalange_swingcenter("finger", f, s)

            proximal_bones = metabones_get_segment_siblings(mbs, "finger", 2, suffixletter)

            hand = mbs["hand.%s" % suffixletter]
            if not hand:
                hand = metabones_add_hand(mbs, suffixletter, proximal_bones, meta_armature_obj.bepuik_autorig.use_thumb)

            hand.use_bepuik = True
            hand.bepuik_ball_socket_rigidity = BEPUIK_BALL_SOCKET_RIGIDITY_DEFAULT

            if meta_armature_obj.bepuik_autorig.use_simple_hand:
                hand.use_deform = True

            hand_width_world = max((proximal_bones[0].head - proximal_bones[len(proximal_bones) - 1].head).length, hand.length())

            hand_width_local = hand_width_world / hand.length()

            hand_custom_shape_name = "%s.%s" % (WIDGET_HAND, suffixletter)

            custom_widget_data[hand_custom_shape_name] = widgetdata_pad(width=hand_width_local * .75, length=.75, mid=0)
            custom_widget_data[hand_custom_shape_name].subsurface_levels = 1

            hand_target_custom_shape_name = "%s target.%s" % (WIDGET_HAND, suffixletter)
            custom_widget_data[hand_target_custom_shape_name] = widgetdata_pad(width=hand_width_local * 1.4,
                                                                               length=1.0 * 1.2, mid=.1)

            hand.custom_shape = widget_get(hand_custom_shape_name)
            hand.show_wire = True

            hand_target = mbs.new_bone("hand target.%s" % suffixletter)
            hand_target.parent = root
            hand_target.head = hand.head.copy()
            hand_target.tail = hand.tail.copy()
            hand_target.custom_shape = widget_get(hand_target_custom_shape_name)
            hand_target.show_wire = True
            hand_target.align_roll = hand.align_roll.copy()

            rig_target_affected(hand_target, hand, position_rigidity=1, orientation_rigidity=1)

            s1_swings = [0, 0, 0, 20, 20]

            for f in range(1, 6):
                s1 = get_finger_segment(f, 1)
                s2 = get_finger_segment(f, 2)
                s3 = get_finger_segment(f, 3)
                s4 = get_finger_segment(f, 4)

                if s1: #valid for s1 to not exist if using simple hand
                    s1.swing = s1_swings[f - 1]

                if not all((s2, s3, s4)):
                    continue

                s3.swing_center = create_finger_swingcenter(f, 3)

                s4.swing_center = create_finger_swingcenter(f, 4)

                if f == 1 and meta_armature_obj.bepuik_autorig.use_thumb:
                    s2.swing_y = 30

                    s3.swing_angle_max = 20
                    s3.swing_angle_min = -85

                    s4.swing_angle_max = 80
                    s4.swing_angle_min = -60
                else:
                    s2.swing_x = 30
                    s2.swing_y = 90

                    s3.swing_angle_max = 0
                    s3.swing_angle_min = -135

                    s4.swing_angle_max = 45
                    s4.swing_angle_min = -95

                if meta_armature_obj.bepuik_autorig.use_simple_hand:
                    rig_simple_finger(hand, s2, s3, s4)

                else:
                    rig_finger(hand, s1, s2, s3, s4)

                    if s1.swing:
                        rot_target = rig_new_target(mbs, "%s rot.%s" % (split_suffix(s1.name)[0], suffixletter),
                                                    controlledmetabone=s1,
                                                    parent=hand_target, lock_location=(True, True, True), lock_rotation= (False, True, True),
                                                    rotation_mode='XYZ')

                        #limiting the location negates the "Inactive Targets Follow" effect, which doesn't make sense for
                        #this target
                        mbc = rot_target.new_meta_blender_constraint('LIMIT_LOCATION')
                        mbc.use_min_x = True
                        mbc.use_max_x = True
                        mbc.use_min_y = True
                        mbc.use_max_y = True
                        mbc.use_min_z = True
                        mbc.use_max_z = True
                        mbc.owner_space = 'LOCAL'
                        mbc.use_transform_limit = True

        def rig_foot():
            def get_toe_segment(f, s):
                return get_phalange_segment("toe", f, s)

            def create_toe_swingcenter(f, s):
                return create_phalange_swingcenter("toe", f, s)

            s1_bones = metabones_get_segment_siblings(mbs, "toe", 1, suffixletter)

            if len(s1_bones) > 1:
                foot_width_world = (s1_bones[0].head - s1_bones[len(s1_bones) - 1].head).length
            elif heel_bone:
                foot_width_world = heel_bone.length()
            else:
                foot_width_world = foot.length() / 2

            multitarget_segments = s1_bones
            final_segments = get_final_segments("toe")
            final_segments_tail_average = sum_vectors([metabone.tail for metabone in final_segments]) / len(
                final_segments)

            #            heel = mbs.new_bone("MCH-heel.%s" % suffixletter)
            #            heel.head = foot.head.copy()
            #            heel.tail = foot_target.head.copy()
            #            flag_bone_mechanical(heel)
            #            heel.align_roll = Vector((0,-1,0))
            #            heel.parent = foot

            foot_target = mbs.new_bone("foot target.%s" % suffixletter)
            foot_target.head = heel_bone.center()
            foot_target.tail = Vector((foot.tail[0], foot.tail[1], 0))
            foot_target_custom_shape_name = "%s target.%s" % (WIDGET_FOOT, suffixletter)
            custom_widget_data[foot_target_custom_shape_name] = widgetdata_pad(
                width=foot_width_world / foot_target.length(), length=1.0, mid=.3)
            foot_target.show_wire = True
            foot_target.custom_shape = widget_get(foot_target_custom_shape_name)
            foot_target.parent = root

            rig_target_affected(foot_target, foot, hard_rigidity=True, use_rest_offset=True)

            #the heel bone is only needed as a reference, after it's used
            #delete it because the final rig doesn't need it.
            if heel_bone:
                mbs.pop(heel_bone.name)

            toes_target = mbs.new_bone("toes target.%s" % suffixletter)
            toes_target.head = foot_target.tail.copy()
            toes_target.tail = final_segments_tail_average.copy()
            toes_target.tail = toes_target.head + (foot_target.y_axis() * toes_target.length())
            toes_target.parent = root
            toes_target.align_roll = sum_vectors([s1.align_roll for s1 in s1_bones]) / len(s1_bones)

            toes_width_local = foot_width_world / toes_target.length()

            toes_target_custom_shape_name = "%s target.%s" % (WIDGET_TOES, suffixletter)
            custom_widget_data[toes_target_custom_shape_name] = widgetdata_pad(width=toes_width_local * 1.2, length=1.2,
                                                                               mid=.1)
            toes_target.show_wire = True
            toes_target.custom_shape = widget_get(toes_target_custom_shape_name)

            #            floor = mbs.new_bone("floor.%s" % suffixletter)
            #            floor.head = foot_target.head.copy()
            #            floor.tail = foot_target.tail.copy()
            #            floor.parent = root
            #            floor.custom_shape = widget_get(WIDGET_FLOOR)#"%s.%s" % (WIDGET_FLOOR,suffixletter))
            #            floor.use_bepuik = True
            #
            #            floor_target = mbs.new_bone("foot floor target.%s" % suffixletter)
            #            floor_target.head = foot_target.head.copy()
            #            floor_target.tail = foot_target.tail.copy()
            #            floor_target.parent = root
            #            floor_target.custom_shape = widget_get(WIDGET_FLOOR)#"%s.%s" % (WIDGET_FLOOR_TARGET,suffixletter))
            #            floor_target.show_wire = True

            #            c = rig_target_affected(floor_target, floor)

            #            #floor affect ball of the foot
            #            c = floor.new_meta_blender_constraint('BEPUIK_LINEAR_AXIS_LIMIT',foot)
            #            c.line_anchor = floor, 0
            #            c.line_direction = floor, 'Z'
            #            c.anchor_b = foot, 1
            #            c.max_distance = 999999
            #
            #            #floor affect heel of the foot
            #            c = floor.new_meta_blender_constraint('BEPUIK_LINEAR_AXIS_LIMIT',foot)
            #            c.line_anchor = floor, 0
            #            c.line_direction = floor, 'Z'
            #            c.anchor_b = heel, 1
            #            c.max_distance = 999999
            #
            #            def tail_affected_by_floor(segment):
            #                c = floor.new_meta_blender_constraint('BEPUIK_LINEAR_AXIS_LIMIT',segment)
            #                c.line_anchor = floor, 0
            #                c.line_direction = floor, 'Z'
            #                c.anchor_b = segment, 1
            #                c.max_distance = 999999

            for f in range(1, 6):
                s1 = get_toe_segment(f, 1)
                s2 = get_toe_segment(f, 2)
                s3 = get_toe_segment(f, 3)

                if not s1:
                    continue

                #                tail_affected_by_floor(s1)

                s1.swing_x = 20
                s1.swing_y = 90

                if s2:
                    s2.swing_center = create_toe_swingcenter(f, 2)
                    s2.swing_angle_max = 0
                    s2.swing_angle_min = -90

                #                    tail_affected_by_floor(s2)

                if s3:
                    s3.swing_center = create_toe_swingcenter(f, 3)
                    s3.swing_angle_max = 70
                    s3.swing_angle_min = -20

                #                    tail_affected_by_floor(s3)

                rig_twist_joint(foot, s1)
                rig_ballsocket_joint(foot, s1)
                rig_bone_to_bone_with_2d_swing_info(foot, s1, axis_a_override=s1)
                rig_toe(s1, s2, s3)
                s1.parent = foot

            for multitarget_segment in multitarget_segments:
                rig_target_affected(toes_target, multitarget_segment, use_rest_offset=True)

            rig_new_target(mbs, "foot ball target.%s" % suffixletter, foot, root, headtotail=1.0, use_rest_offset=True)

        if eye:
            eye.new_meta_blender_constraint('DAMPED_TRACK', eye_target)
            eye.use_deform = True
            eye.parent = head

        if ear:
            ear.parent = head

        rig_arm(shoulder, uparm, loarm, relative_x_axis, up)
        rig_new_target(mbs, name="loarm target.%s" % suffixletter, controlledmetabone=loarm, parent=root)
        rig_chest_to_shoulder(chest, shoulder, relative_x_axis)
        rig_hand()

        rig_leg(upleg, loleg, foot, leg_relative_x_axis)
        rig_new_target(mbs, name="loleg target.%s" % suffixletter, controlledmetabone=loleg, parent=root)

        rig_foot()

        measure = mbs.new_bone("MCH-leg twist measure axis.%s" % suffixletter, transform=measurement_axis_mat)
        rig_hips_to_upleg(hips, upleg, hips, measure, leg_relative_x_axis)

    rig_side("L")
    rig_side("R")

    bpy.ops.object.mode_set(mode='EDIT')

    mbs.to_ob(rig_ob)

    prop = rna_idprop_ui_prop_get(rig_ob.pose.bones["spine"], "torso stiffness", create=True)
    prop["min"] = 0.0
    prop["soft_min"] = 0.0
    prop["soft_max"] = 2.0

    rig_ob.pose.bones["spine"]["torso stiffness"] = 2.0

    def add_angular_joint_driver(driven_bone_name, driven_constraint_name):
        fcurve = rig_ob.pose.bones[driven_bone_name].constraints[driven_constraint_name].driver_add("bepuik_rigidity")
        fcurve.modifiers.remove(fcurve.modifiers[0])
        driver = fcurve.driver
        driver.type = 'AVERAGE'
        v = driver.variables.new()
        v.type = 'SINGLE_PROP'
        v.targets[0].id = rig_ob
        v.targets[0].data_path = r'pose.bones["spine"]["torso stiffness"]'

    add_angular_joint_driver(hips.name, spine_stiff_angular_joint.name)
    add_angular_joint_driver(spine.name, chest_stiff_angular_joint.name)

    organize_pchan_layers(rig_ob)
    rig_ob.bepuik_autorig.is_meta_armature = False
    rig_ob.bepuik_autorig.is_auto_rig = True
    rig_ob.use_bepuik_solve_peripheral_bones = False
    apply_rig_starting_layers(rig_ob)

    found_error = False
    found_warning = False
    for warninglevel, msg in printmsgs:
        if warninglevel == 'ERROR':
            found_error = True
        elif warninglevel == 'WARNING':
            found_warning = True

        if op:
            op.report({warninglevel}, msg)

    if not found_error and not found_warning:
        op.report({'INFO'}, "Rig Completed successfully!")

    return rig_ob


def rig_new_target(metabonegroup, name, controlledmetabone, parent, scale=.10, headtotail=0,
                   custom_shape_name=WIDGET_CUBE, lock_location=(False, False, False), lock_rotation_w=False,
                   lock_rotation=(False, False, False), lock_rotations_4d=False, custom_widget_data=None,
                   use_rest_offset=True, rotation_mode='QUATERNION'):
    targetmetabone = metabonegroup.new_bone_by_fraction(name=name, source_metabone=controlledmetabone,
                                                        start_fraction=headtotail, end_fraction=headtotail + scale)

    targetmetabone.parent = parent
    targetmetabone.show_wire = True
    targetmetabone.custom_shape = widgetdata_get(custom_shape_name, custom_widget_data)
    targetmetabone.lock_scale = (True, True, True)
    targetmetabone.lock_rotation_w = lock_rotation_w
    targetmetabone.lock_rotation = lock_rotation
    targetmetabone.lock_rotations_4d = lock_rotations_4d
    targetmetabone.lock_location = lock_location
    targetmetabone.rotation_mode = rotation_mode

    rig_target_affected(targetmetabone, controlledmetabone, headtotail=headtotail, use_rest_offset=use_rest_offset)

    return targetmetabone


def flag_bone_mechanical(mechanical_bone):
    mechanical_bone.lock_rotation = (True, True, True)
    mechanical_bone.lock_location = (True, True, True)
    mechanical_bone.lock_scale = (True, True, True)
    mechanical_bone.lock_rotation_w = True

    if not mechanical_bone.name.startswith("MCH-"):
        mechanical_bone.name = "MCH-%s" % mechanical_bone.name


def rig_hips_to_upleg(hips, upleg, upleg_parent, measurement_axis, relative_x_axis):
    """
    :arg hips:
    :type hips: MetaBone
    :arg upleg:
    :type upleg: MetaBone
    :arg upleg_parent:
    :type upleg_parent: MetaBone
    :arg measurement_axis:
    :type measurement_axis: MetaBone
    :arg relative_x_axis: either 'X' or 'NEGATIVE_X'
    :type relative_x_axis: str
    """
    flag_bone_mechanical(measurement_axis)
    measurement_axis.parent = hips

    upleg.use_deform = True
    upleg.parent = upleg_parent
    upleg.use_bepuik_always_solve = True

    c = hips.new_meta_blender_constraint('BEPUIK_TWIST_LIMIT', upleg, name="%s twist limit" % upleg.name)
    c.axis_a = hips, 'Y'
    c.axis_b = hips, 'Y'
    c.measurement_axis_a = measurement_axis, 'Y'
    c.measurement_axis_b = hips, 'Z'
    c.max_twist = 120

    if upleg_parent == hips:
        flag_bone_deforming_ballsocket_bepuik(upleg)
        upleg.use_inherit_rotation = False
    else:
        c = hips.new_meta_blender_constraint('BEPUIK_BALL_SOCKET_JOINT', upleg)
        c.anchor = upleg, 0

    #prevent leg from going too far up
    c = hips.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', upleg, name="%s swing up limit" % upleg.name)
    c.axis_a = upleg, 'Y'
    c.axis_b = upleg, 'Y'
    c.max_swing = 120

    #prevent leg from going too far back
    c = hips.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', upleg, name="%s swing back limit" % upleg.name)
    c.axis_a = upleg, 'Z'
    c.axis_b = upleg, 'Y'
    c.max_swing = 165

    #prevent leg from going too far to the opposite side
    #c = hips.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', upleg, name="%s swing side limit" % upleg.name)
    #c.axis_a = upleg, relative_x_axis
    #c.axis_b = upleg, 'Y'
    #c.max_swing = 110


def rig_bone_to_bone_revolute_swing_center(fa, fb, swing_center, swing_angle_max, swing_angle_min):
    c = fa.new_meta_blender_constraint('BEPUIK_REVOLUTE_JOINT', fb)
    c.free_axis = fa, 'X'

    m = fa.matrix() * Matrix.Rotation(math.radians((swing_angle_max + swing_angle_min) / 2), 4, 'X')
    swing_center.head = fa.tail.copy()
    swing_center.tail = fa.tail.copy() + (vector4_to_vector3(m.col[1]) * fa.length())
    swing_center.parent = fa
    flag_bone_mechanical(swing_center)

    c = fa.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', fb)
    c.axis_a = swing_center, 'Y'
    c.axis_b = fb, 'Y'
    c.max_swing = abs(swing_angle_max - swing_angle_min) / 2


def rig_twist_joint(a, b, axis_a_override=None):
    if not axis_a_override:
        axis_a_override = a

    c = a.new_meta_blender_constraint('BEPUIK_TWIST_JOINT', b)
    c.axis_a = axis_a_override, 'Y'
    c.axis_b = b, 'Y'


def rig_ballsocket_joint(a, b):
    c = a.new_meta_blender_constraint('BEPUIK_BALL_SOCKET_JOINT', b)
    c.anchor = b, 0


def rig_bone_to_bone_with_swing_center_info(s, s_with_swing):
    rig_bone_to_bone_revolute_swing_center(s, s_with_swing, s_with_swing.swing_center, s_with_swing.swing_angle_max,
                                           s_with_swing.swing_angle_min)


def rig_bone_to_bone_with_2d_swing_info(a, b, axis_a_override=None):
    if not axis_a_override:
        axis_a_override = a

    if hasattr(b, 'swing_y'):
        c = a.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', b)
        c.axis_a = b, 'Y'
        c.axis_b = b, 'Y'
        c.max_swing = b.swing_y

    if hasattr(b, 'swing_x'):
        c = a.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', b)
        c.axis_a = b, 'X'
        c.axis_b = b, 'X'
        c.max_swing = b.swing_x


def rig_simple_finger(hand, proximal, intermediate, distal):
    proximal.use_connect = False
    proximal.parent = hand
    rig_twist_joint(proximal.parent, proximal)
    rig_bone_to_bone_with_2d_swing_info(proximal.parent, proximal, axis_a_override=None)
    flag_bone_deforming_ballsocket_bepuik(proximal)

    rig_twist_joint(proximal, intermediate)
    rig_bone_to_bone_with_swing_center_info(proximal, intermediate)
    flag_bone_deforming_ballsocket_bepuik(intermediate)
    intermediate.use_connect = True
    intermediate.parent = proximal

    rig_twist_joint(intermediate, distal)
    rig_bone_to_bone_with_swing_center_info(intermediate, distal)
    flag_bone_deforming_ballsocket_bepuik(distal)
    distal.use_connect = True
    distal.parent = intermediate

def rig_finger(hand, metacarpal, proximal, intermediate, distal):
    metacarpal.parent = hand

    #s1 is the palm bone
    if metacarpal.swing:
        flag_bone_deforming_ballsocket_bepuik(metacarpal)

        c = hand.new_meta_blender_constraint('BEPUIK_REVOLUTE_JOINT', metacarpal)
        c.free_axis = hand, 'X'

        c = hand.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', metacarpal)
        c.axis_a = hand, 'Y'
        c.axis_b = metacarpal, 'Y'
        c.max_swing = max(degrees_between(hand, metacarpal), metacarpal.swing)

        #since s1 has a swing, s2 will be its child
        s2_parent = metacarpal
        proximal.use_connect = True
    else:
        #s1 doesn't have a swing, therefore, it should simply be a deforming mechanical bone.
        metacarpal.use_deform = True
        flag_bone_mechanical(metacarpal)

        s2_parent = hand
        proximal.use_connect = False

    proximal.parent = s2_parent

    rig_twist_joint(proximal.parent, proximal)
    rig_bone_to_bone_with_2d_swing_info(proximal.parent, proximal, axis_a_override=None)
    flag_bone_deforming_ballsocket_bepuik(proximal)

    rig_twist_joint(proximal, intermediate)
    rig_bone_to_bone_with_swing_center_info(proximal, intermediate)
    flag_bone_deforming_ballsocket_bepuik(intermediate)
    intermediate.use_connect = True
    intermediate.parent = proximal

    rig_twist_joint(intermediate, distal)
    rig_bone_to_bone_with_swing_center_info(intermediate, distal)
    flag_bone_deforming_ballsocket_bepuik(distal)
    distal.use_connect = True
    distal.parent = intermediate


def rig_toe(s1, s2, s3):
    flag_bone_deforming_ballsocket_bepuik(s1)

    if s2:
        s2.use_connect = True
        s2.parent = s1

        rig_twist_joint(s1, s2)
        rig_bone_to_bone_with_swing_center_info(s1, s2)
        flag_bone_deforming_ballsocket_bepuik(s2)

    if s3:
        s3.use_connect = True
        s3.parent = s2

        rig_twist_joint(s2, s3)
        rig_bone_to_bone_with_swing_center_info(s2, s3)
        flag_bone_deforming_ballsocket_bepuik(s3)


def rig_leg(upleg, loleg, foot, relative_x_axis='X'):
    flag_bone_deforming_ballsocket_bepuik(upleg)

    flag_bone_deforming_ballsocket_bepuik(loleg)
    loleg.use_connect = True
    loleg.bepuik_ball_socket_rigidity = 50

    flag_bone_deforming_ballsocket_bepuik(foot)
    foot.use_connect = True
    foot.bepuik_ball_socket_rigidity = 200

    #upleg to loleg connections
    rig_twist_limit(upleg, loleg, 10)

    antiparallel_limiter(upleg, loleg)

    c = upleg.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', loleg)
    c.axis_a = upleg, 'NEGATIVE_Z'
    c.axis_b = loleg, 'Y'
    #the 85 here helps prevent knee locking
    c.max_swing = max(degrees_between(loleg, -upleg.z_axis()), 85)

    c = upleg.new_meta_blender_constraint('BEPUIK_SWIVEL_HINGE_JOINT', loleg)
    c.hinge_axis = loleg, relative_x_axis
    c.twist_axis = loleg, 'Y'

    loleg.parent = upleg

    #loleg to foot connections
    rig_twist_limit(loleg, foot, 10)
    rig_swing_limit(loleg, foot, 75)

    foot.parent = loleg


def flag_bone_deforming_ballsocket_bepuik(metabone):
    metabone.use_deform = True
    metabone.use_bepuik = True
    metabone.bepuik_ball_socket_rigidity = BEPUIK_BALL_SOCKET_RIGIDITY_DEFAULT


def antiparallel_limiter(a, b, degrees=20):
    c = a.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', b)
    c.axis_a = a, 'Y'
    c.axis_b = b, 'Y'
    c.max_swing = 180 - degrees


def rig_arm(shoulder, uparm, loarm, relative_x_axis, up=Vector((0, 0, 1))):
    shoulder.use_bepuik = True
    shoulder.use_deform = True
    shoulder.bepuik_ball_socket_rigidity = 0
    shoulder.bepuik_rotational_heaviness = 35

    uparm.use_connect = True
    flag_bone_deforming_ballsocket_bepuik(uparm)

    loarm.bbone_segments = 32
    loarm.bbone_out = 0
    loarm.bbone_in = 0
    loarm.use_connect = True
    flag_bone_deforming_ballsocket_bepuik(loarm)

    antiparallel_limiter(shoulder, uparm, 30)

    c = uparm.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', loarm)
    c.axis_a = uparm, relative_x_axis
    c.axis_b = loarm, 'Y'
    if relative_x_axis == 'X':
        scalar = 1
    else:
        scalar = -1

    #87 prevents arm locking in most cases
    c.max_swing = max(degrees_between(scalar*uparm.x_axis(), loarm), 87)

    antiparallel_limiter(uparm, loarm)

    c = uparm.new_meta_blender_constraint('BEPUIK_REVOLUTE_JOINT', loarm)
    c.free_axis = uparm, 'Z'


def rig_chest_to_shoulder(chest, shoulder, relative_x_axis):
    shoulder.parent = chest
    shoulder.use_connect = False
    shoulder.bepuik_ball_socket_rigidity = 16

    c = chest.new_meta_blender_constraint('BEPUIK_TWIST_JOINT', shoulder)
    c.axis_a = shoulder, 'Y'
    c.axis_b = shoulder, 'Y'

    #prevents the shoulder from going too far up
    c = chest.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', shoulder)
    c.axis_a = shoulder, 'Y'
    c.axis_b = shoulder, 'Y'
    c.max_swing = 45

    #prevents the shoulder from going too far down
    c = chest.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', shoulder)
    c.axis_a = shoulder, 'Z'
    c.axis_b = shoulder, 'Y'
    c.max_swing = 95

    #prevents the shoulder from going too far forward or back
    c = chest.new_meta_blender_constraint('BEPUIK_SWING_LIMIT', shoulder)
    c.axis_a = shoulder, relative_x_axis
    c.axis_b = shoulder, relative_x_axis
    c.max_swing = 22


def get_pchan_target_names(ob):
    pchan_target_names = set()
    for pchan in ob.pose.bones:
        for con in pchan.constraints:
            if con.type == 'BEPUIK_CONTROL':
                if con.connection_subtarget:
                    pchan_target_names.add(con.connection_subtarget)

    return pchan_target_names


def organize_pchan_layer(pchan, bone_hint_str=None, is_bepuik_target=False):
    bone = pchan.bone
    suffixletter = get_suffix_letter(bone.name)
    layer_indices = set()
    exclude_from_body_layers = False

    if bone.use_deform:
        layer_indices.add(AL_DEFORMER)

    if pchan.use_bepuik:
        layer_indices.add(AL_BEPUIK_BONE)

    if is_bepuik_target or pchan.name.endswith("target"):
        layer_indices.add(AL_TARGET)

    if (pchan.rotation_mode == 'QUATERNION' or pchan.rotation_mode == 'AXIS_ANGLE') and pchan.lock_rotations_4d:
        lock_rotation = (all(pchan.lock_rotation) and pchan.lock_rotation_w)
    else:
        lock_rotation = (all(pchan.lock_rotation))

    if not lock_rotation or not all(pchan.lock_scale) or not all(pchan.lock_location):
        layer_indices.add(AL_ANIMATABLE)
    else:
        layer_indices.add(AL_MECHANICAL)
        exclude_from_body_layers = True

    #    if pchan.name.startswith("MCH-"):
    #        layer_indices.add(AL_MECHANICAL)
    #        exclude_from_body_layers = True

    if not exclude_from_body_layers:
        if not bone_hint_str:
            bone_hint_str = bone.basename

        for substring_set in SUBSTRING_SETS:
            if any(substring in bone_hint_str for substring in substring_set):
                if (substring_set, suffixletter) in MAP_SUBSTRING_SET_TO_ARMATURELAYER:
                    index_to_add = MAP_SUBSTRING_SET_TO_ARMATURELAYER[(substring_set, suffixletter)]
                    layer_indices.add(index_to_add)

    bone.layers = [True if i in layer_indices else False for i in range(32)]


def organize_pchan_layers(ob):
    pchan_target_names = get_pchan_target_names(ob)
    for pchan in ob.pose.bones:
        organize_pchan_layer(pchan, is_bepuik_target=pchan.name in pchan_target_names)

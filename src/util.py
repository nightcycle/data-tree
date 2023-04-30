from luau.convert import from_dict, mark_as_literal
from typing import Any, Literal
import json
import dpath
import os
import sys

TYPE_CONVERSIONS = {
	"Vector3": ["Vector3", "Vector3Integer", "Vector3Double"],
	"Vector2": ["Vector2", "Vector2Integer", "Vector2Double"],
	"number": ["Integer", "int", "Float", "float", "Double", "double", "number"],
	"string": ["string"],
	"Color3": ["Color3"],
	"boolean": ["boolean"],
	"CFrame": ["CFrameIncrement", "CFrame", "CFrameInteger", "CFrameDouble"],
	"DateTime": ["DateTime"]
}

KEY_TYPE_MARKER = "::"

AcceptedType = Literal[
	"boolean",
	"Color3", 
	"Double",
	"double",
	"float", 
	"Float",
	"Integer", 
	"int", 
	"string",
	"DateTime", 
	"Vector3",
	"Vector3Integer",
	"Vector3Double",
	"Vector2",
	"Vector2Integer",
	"Vector2Double",
	"CFrame",
	"CFrameDouble",
	"CFrameInteger",
]

def get_package_zip_path() -> str:
	base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
	print(base_path)
	for sub_path in os.listdir(base_path):
		print(sub_path)

	return os.path.join(base_path, "data\\Packages.zip")

def get_if_standard_type(type_name: str) -> bool:
	# print("TYPE", type_name)
	untyped_AcceptedType: Any = AcceptedType
	return (type_name in untyped_AcceptedType.__args__) or (type_name[0:5] == "Enum.")
	
def get_if_optional(type_name: str) -> bool:
	return type_name[len(type_name)-1] == "?"

def get_raw_type_name(type_name: str) -> str:
	if get_if_optional(type_name):
		return type_name[0:(len(type_name)-1)]
	else:
		return type_name

def write_standard_value_from_config(config_val: Any, val_type: AcceptedType) -> str:
	if config_val == "nil":
		return "nil"
	raw_val_type = get_raw_type_name(val_type)
	if raw_val_type == "Color3":
		if type(config_val) == str: # hex value
			if config_val[0] == "#":
				config_val = config_val[1:]

			return f"Color3.fromHex(\"#{config_val}\")"

		elif "H" in config_val or "H::int" in config_val: # hsv value
			h = 0
			s = 0
			v = 0

			if "H" in config_val:
				h = config_val["H"]
				s = config_val["S"]
				v = config_val["V"]
			elif "H::int" in config_val:
				h = config_val["H::int"]
				s = config_val["S::int"]
				v = config_val["V::int"]
			
			return f"Color3.fromHSV({h}, {s}, {v})"
		elif "R" in config_val or "R::int" in config_val: # rgb value
			r = 0
			g = 0
			b = 0
			
			if "R" in config_val:
				r = config_val["R"]
				g = config_val["G"]
				b = config_val["B"]
			elif "R::int" in config_val:
				r = config_val["R::int"]
				g = config_val["G::int"]
				b = config_val["B::int"]
			
			return f"Color3.fromRGB({r}, {g}, {b})"

	elif raw_val_type == "Double" or raw_val_type == "double":
		return f"math.round(100*{config_val})/100"

	elif raw_val_type == "float" or raw_val_type == "Float":
		return f"{config_val}"

	elif raw_val_type == "int" or raw_val_type == "Integer":
		return f"math.round({config_val})"

	elif raw_val_type == "boolean":
		if config_val == True:
			return "true"
		else:
			return "false"
	elif raw_val_type == "string":
		if "{DISPLAY_NAME}" in config_val:
			final_text = config_val.replace("{DISPLAY_NAME}", "\"..player.DisplayName..\"")
			return f"\"{final_text}\""
		elif "{USER_NAME}" in config_val:
			final_text = config_val.replace("{USER_NAME}", "\"..player.Name..\"")
			return f"\"{final_text}\""
		elif "{USER_ID}" in config_val:
			final_text = config_val.replace("{USER_ID}", "\"..player.UserId..\"")
			return f"\"{final_text}\""
		elif "{GUID}" in config_val:
			final_text = config_val.replace("{GUID}", f"\"..game:GetService(\"HttpService\"):GenerateGUID(false)..\"")
			return f"\"{final_text}\""
		else:		
			return f"\"{config_val}\""

	elif raw_val_type == "DateTime":
		if config_val == "NOW":
			return f"DateTime.now()"
		elif type(config_val) == int:
			return f"DateTime.fromUnixTimestamp({config_val})"
		elif type(config_val) == float:
			return f"DateTime.fromUnixTimestampMillis(math.round({config_val}*1000))"
		elif type(config_val) == dict:
			iso_string = ""
			if "Year" in config_val:
				iso_string += "{0:04d}".format(round(config_val["Year"]))
			else:
				iso_string += "{0:04d}".format(1970)

			iso_string += "-"
			if "Month" in config_val:
				iso_string += "{0:02d}".format(round(config_val["Month"]))
			else:
				iso_string += "{0:02d}".format(1)

			iso_string += "-"
			if "Day" in config_val:
				iso_string += "{0:02d}".format(round(config_val["Day"]))
			else:
				iso_string += "{0:02d}".format(1)

			iso_string += "T"
			if "Hour" in config_val:
				iso_string += "{0:02d}".format(round(config_val["Hour"]))
			else:
				iso_string += "{0:02d}".format(0)

			iso_string += ":"
			if "Minute" in config_val:
				iso_string += "{0:02d}".format(round(config_val["Minute"]))
			else:
				iso_string += "{0:02d}".format(0)

			iso_string += ":"
			if "Second" in config_val:
				iso_string += "{0:02d}".format(round(config_val["Second"]))
			else:
				iso_string += "{0:02d}".format(0)

			iso_string += "Z"

			return f"DateTime.fromIsoDate(\"{iso_string}\")"
	elif raw_val_type == "Vector3" or raw_val_type == "Vector3Integer" or raw_val_type == "Vector3Double":
	
		x = config_val["X"]
		y = config_val["Y"]
		z = config_val["Z"]

		if raw_val_type == "Vector3Double":
			return f"Vector3.new(math.round({x}*100)/100, math.round({y}*100)/100, math.round({z}*100)/100)"
		elif raw_val_type == "Vector3Integer":
			return f"Vector3.new(math.round({x}), math.round({y}), math.round({z}))"
		else:
			return f"Vector3.new({x}, {y}, {z})"
	
	elif raw_val_type == "Vector2" or raw_val_type == "Vector2Integer" or raw_val_type == "Vector2Double":
	
		x = config_val["X"]
		y = config_val["Y"]
	
		if raw_val_type == "Vector2Double":
			return f"Vector2.new(math.round({x}*100)/100, math.round({y}*100)/100)"
		elif raw_val_type == "Vector2Integer":
			return f"Vector2.new(math.round({x}), math.round({y}))"
		else:
			return f"Vector2.new({x}, {y})"

	elif raw_val_type == "CFrame" or raw_val_type == "CFrameDouble" or raw_val_type == "CFrameInteger":
		position = config_val["Position"]
		euler_angle_yxz = config_val["EulerAngleYXZ"]

		rX = euler_angle_yxz["X"]
		rY = euler_angle_yxz["Y"]
		rZ = euler_angle_yxz["Z"]

		pX = position["X"]
		pY = position["Y"]
		pZ = position["Z"]

		if raw_val_type == "CFrameDouble":
			return f"CFrame.fromEulerAnglesYXZ(math.round({rX}*100)/100, math.round({rY}*100)/100, math.round({rZ}*100)/100) + Vector3.new(math.round({pX}*100)/100, math.round({pY}*100)/100, math.round({pZ}*100)/100)"
		elif raw_val_type == "CFrameInteger":
			return f"CFrame.fromEulerAnglesYXZ(math.round({rX}), math.round({rY}), math.round({rZ})) + Vector3.new(math.round({pX}), math.round({pY}), math.round({pZ}))"
		else:
			return f"CFrame.fromEulerAnglesYXZ({rX}, {rY}, {rZ}) + Vector3.new({pX}, {pY}, {pZ})"
	elif raw_val_type[0:5] == "Enum.":
		return f"{raw_val_type}.{config_val}"

	raise ValueError(f"Bad initial type: {val_type} with config value {json.dumps(config_val, indent=5)}")


def write_custom_value_from_config(config_val: Any, type_name: str, config_types: dict[str, list | dict]) -> str:

	if config_val == "nil":
		return "nil"

	if "List[" in type_name:
		out_list = ["{"]
		untyped_inner_type_name: Any = type_name.replace("List[", "").replace("]", "")
		inner_type_name: AcceptedType = untyped_inner_type_name
		for v in config_val:
			out_list.append(write_value_from_config(v, inner_type_name, config_types)+",")
		out_list.append("}")
		
		return "\n".join(out_list)

	elif "Dict[" in type_name:
		out = {}
		inner_type_names = ((type_name.replace("Dict[", "")).replace("]", "")).split(",")
		key_type_name = inner_type_names[0].replace(" ", "")
		untyped_val_type_name: Any = inner_type_names[1].replace(" ", "")
		val_type_name: AcceptedType = untyped_val_type_name
		for k, v in config_val.items():
			if get_roblox_type(key_type_name) == "number":
				num_str = mark_as_literal(f"[{k}]")
				out[num_str] = mark_as_literal(write_value_from_config(v, val_type_name, config_types))
			else:
				out[k] = mark_as_literal(write_value_from_config(v, val_type_name, config_types))
		return from_dict(out, skip_initial_indent=True)
	else:
		raw_type_name = get_raw_type_name(type_name)
		untyped_val_def: Any = config_types[raw_type_name]
		val_def: dict = untyped_val_def
		if type(config_types[raw_type_name]) == list:
			if config_val in val_def:
				return f"\"{config_val}\""
			else:
				raise ValueError(f"config val {config_val} is not a valid option for type {raw_type_name}")		
		else:
			out = {}
			for type_path, potential_type_name in dpath.search(val_def, '**', yielded=True):
				
				if type(potential_type_name) == str:
					untyped_sub_type_name: Any = potential_type_name
					sub_type_name: AcceptedType = untyped_sub_type_name
					current_val = dpath.get(config_val, type_path, default=None)
					if current_val != None:
						if get_if_optional(sub_type_name) or current_val != "nil":
							dpath.new(out, type_path, mark_as_literal(write_value_from_config(current_val, sub_type_name, config_types)))
						else:
							dpath.new(out, type_path, mark_as_literal("nil"))
					elif get_if_optional(sub_type_name):
						dpath.new(out, type_path, mark_as_literal("nil"))
			return from_dict(out, skip_initial_indent=False) + f" :: {raw_type_name}"

def write_value_from_config(config_val: Any, type_name: AcceptedType, config_types: dict[str, list | dict]) -> str:
	if get_if_standard_type(get_raw_type_name(type_name)):
		return write_standard_value_from_config(config_val, type_name)
	else:
		return write_custom_value_from_config(config_val, type_name, config_types)
		

def get_type_name_from_key(key: str) -> str | None:
	if KEY_TYPE_MARKER in key:
		return key.split(KEY_TYPE_MARKER)[1]
	else:
		return None

def get_raw_key_name(key: str) -> str:
	if KEY_TYPE_MARKER in key:
		return key.split(KEY_TYPE_MARKER)[0]
	else:
		return key

def get_roblox_type(type_name: str) -> str | None:
	question_ending = ""
	if get_if_optional(type_name):
		question_ending = "?"
	
	type_name = get_raw_type_name(type_name)

	for k, options in TYPE_CONVERSIONS.items():
		if type_name in options:
			return k + question_ending
	
	if type_name[0:5] == "List[":
		type_name = type_name[5:]
		type_name = type_name[0:(len(type_name)-1)]
		return "{[number]: "+type_name+"}" + question_ending
	elif type_name[0:5] == "Dict[":
		type_name = type_name[5:]
		type_name = type_name[0:(len(type_name)-1)]
		param_list = type_name.split(",")
		key = param_list[0].replace(" ", "")
		val = param_list[1].replace(" ", "")
		return "{["+key+"]: "+val+"}" + question_ending
	elif type_name[0:5] == "Enum.":
		enum_name = type_name.split(".")[1]
		return "Enum." + enum_name + question_ending

	raise ValueError(f"bad type name: {type_name}")
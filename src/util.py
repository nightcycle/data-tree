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

def get_if_optional(type_name: str) -> bool:
	return type_name[len(type_name)-1] == "?"
	
def get_raw_type_name(type_name: str) -> str:
	if get_if_optional(type_name):
		return type_name[0:(len(type_name)-1)]
	else:
		return type_name

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
		key = param_list[0]
		val = param_list[1]
		return "{["+key+"]: "+val+"}" + question_ending
	elif type_name[0:5] == "Enum.":
		enum_name = type_name.split(".")[1]
		return "Enum." + enum_name + question_ending

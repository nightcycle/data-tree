import dpath
from util import get_if_optional, write_value_from_config, write_standard_value_from_config, get_raw_key_name, get_type_name_from_key, get_roblox_type, get_raw_type_name
from luau import indent_block
from luau.convert import from_dict, mark_as_literal, from_dict_to_type
from luau.roblox import write_script
from luau.roblox.wally import require_roblox_wally_package
from luau.roblox.util import get_module_require
from luau.path import get_if_module_script, remove_all_path_variants
from config import get_data_config, SIGNAL_WALLY_PATH, NETWORK_UTIL_WALLY_PATH, MAID_WALLY_PATH, HEADER_WARNING, GET_SUFFIX_KEY, UPDATE_SUFFIX_KEY
from typing import Any, Literal

def get_if_number_in_path(path: str) -> bool:
	has_num_in_path = False
	for key in path.split("/"):
		try:
			v = int(key)
			has_num_in_path = True
		except:
			key = key + ""
	return has_num_in_path

def build():
	config = get_data_config()

	build_path = config["build"]["out"]["server_path"]
	assert get_if_module_script(build_path), "server datatree must be a ModuleScript, please make sure the server_path only ends with .lua/luau"

	remove_all_path_variants(build_path)

	type_imports = []
	for key in config["types"]:
		type_imports.append(f"export type {key} = DataTypes.{key}")

	type_tree = {}
	func_tree = {}
	enum_deserializers = []
	type_serializers = []
	type_deserializers = []

	def assemble_serializer_function(type_name: str, type_data: dict | list) -> list[str]:
		if type(type_data) == dict:
			serializer_content = [
				f"serializers[\"{type_name}\"] = function(value: {type_name}): string",
			]
			out = {}
			for path, value in dpath.search(type_data, '**', yielded=True):
				if type(value) == str:
					keys = path.split("/")
					key_str = "value"
					for key in keys:
						key_str += "[\""+key+"\"]"
					if value in config["types"]:
						dpath.new(out, path, mark_as_literal(f"serializers[\"{value}\"]({key_str})"))
					else:
						ro_type = get_roblox_type(get_raw_type_name(value))
						if ro_type != None:
							dpath.new(out, path, mark_as_literal(f"serializers[\"{ro_type}\"]({key_str})"))
			
			serializer_content += indent_block(("return HttpService:JSONEncode(" + from_dict(out, skip_initial_indent=True) + ") :: any").split("\n"))
			serializer_content.append("end")

			return serializer_content
		return []

	def assemble_deserializer_function(type_name: str, type_data: dict | list) -> list[str]:
		if type(type_data) == dict:
			deserializer_content = [
				f"deserializers[\"{type_name}\"] = function(value: string): {type_name}",
				"\tlocal data = HttpService:JSONDecode(value)",
			]
			out = {}
			for path, value in dpath.search(type_data, '**', yielded=True):
				if type(value) == str:
					keys = path.split("/")
					key_str = "data"
					for key in keys:
						key_str += "[\""+key+"\"]"
					if value in config["types"]:
						dpath.new(out, path, mark_as_literal(f"deserializers[\"{value}\"]({key_str})"))
					else:
						ro_type = get_roblox_type(get_raw_type_name(value))
						if ro_type != None:
							dpath.new(out, path, mark_as_literal(f"deserializers[\"{ro_type}\"]({key_str})"))
			
			deserializer_content += indent_block(("return " + from_dict(out, skip_initial_indent=True) + " :: any").split("\n"))
			deserializer_content.append("end")

			return deserializer_content
		return []

	for type_name, type_data in config["types"].items():
		type_deserializers += assemble_deserializer_function(type_name, type_data)
		type_serializers += assemble_serializer_function(type_name, type_data)

	def write_enum_deserializer(enum_name: str):
		raw_enum_name = get_raw_type_name(enum_name)
		return [
			f"deserializers[\"Enum.{raw_enum_name}\"] = function(value: number): Enum.{raw_enum_name}",
			f"\tfor i, enumItem in ipairs(Enum.{raw_enum_name}:GetEnumItems()) do if enumItem.Value == value then return enumItem end end",
			f"error(\"No enum item found in {raw_enum_name} for value \"..tostring(value))",
			"end",
		]

	out_variables = {}

	for full_path, value in dpath.search(config["tree"], '**', yielded=True):
		keys = full_path.split("/")
		raw_keys = []
		final_type: None | str = None
		for key in keys:
			if final_type == None:
				raw_keys.append(get_raw_key_name(key))
				final_type = get_type_name_from_key(key)

		path = "/".join(raw_keys)
		
		if final_type != None:
			var_type = get_raw_type_name(final_type)

			if "List[" in var_type:
				var_type = (var_type.replace("List[", "")).replace("]", "")
				var_type = "{[number]:" + var_type + "}"
			if "Dict[" in var_type:
				var_type = (var_type.replace("Dict[", "")).replace("]", "")
				var_type = var_type.replace(",", "]:")
				var_type = "{[" + var_type + "}"
			
			if get_if_optional(final_type):
				var_type += "?"

			var_name = "tree"+get_raw_key_name(full_path.replace("/", ""))+"Val"
			typed_var_name = var_name + ": " + var_type
			if final_type[0:5] == "Enum.":
				enum_deserializers += write_enum_deserializer(final_type[5:])
				initial_value = write_value_from_config(value, final_type, config["types"])
				
				out_variables[typed_var_name] = initial_value
				if value == "nil":
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, serializers[\"{final_type}\"], deserializers[\"{final_type}\"])"))
				else:
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, serializers[\"{final_type}\"], deserializers[\"{final_type}\"])"))

				dpath.new(type_tree, path, mark_as_literal(f"DataHandler<{final_type}, string>"))
			elif final_type[0:5] == "List[":
				if not get_if_number_in_path(full_path):
					initial_value = write_value_from_config(value, final_type, config["types"])
					inner_type = final_type[5:(len(final_type)-1)]
					raw_inner_type = get_raw_type_name(inner_type)
					out_variables[typed_var_name] = initial_value
					# print("LIST", full_path, ": ", inner_type)
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, serializeList(serializers[\"{raw_inner_type}\"]), deserializeList(deserializers[\"{raw_inner_type}\"])) :: any"))
					dpath.new(type_tree, path, mark_as_literal("DataHandler<{[number]: "+inner_type+"}, string>"))

			elif final_type[0:5] == "Dict[":
				if not get_if_number_in_path(full_path):
					initial_value = write_value_from_config(value, final_type, config["types"])
					inner_type = final_type[5:(len(final_type)-1)]
					type_list = inner_type.split(",")
					# print("DICT", full_path, ": ", type_list)
					key = type_list[0]
					val = type_list[1]
					raw_val = get_raw_type_name(val)
					out_variables[typed_var_name] = initial_value
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, serializeDict(serializers[\"{raw_val}\"]), deserializeDict(deserializers[\"{raw_val}\"])) :: any"))
					dpath.new(type_tree, path, mark_as_literal("DataHandler<{["+key+"]: "+val+"}, string>"))
			else:
				ro_type = get_roblox_type(final_type)
				if ro_type == "number":
					dpath.new(func_tree, path, mark_as_literal(f"_newNumberHandler(\"{path}\", {value}, processors[\"{final_type}\"])"))
					dpath.new(type_tree, path, mark_as_literal("NumberDataHandler"))
				else:
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\")"))
					dpath.new(type_tree, path, mark_as_literal(f"DataHandler<{ro_type}, string>"))
		
		elif type(value) == str:
			raw_value = get_raw_type_name(value)
			if raw_value in config["types"]:
				dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", nil, serializers[\"{raw_value}\"], deserializers[\"{raw_value}\"])"))
				dpath.new(type_tree, path, mark_as_literal(f"DataHandler<{final_type}, string>"))
			else:
				value = value.replace("{DISPLAY_NAME}", f"\"..player.DisplayName..\"")
				value = value.replace("{USER_NAME}", f"\"..player.Name..\"")
				value = value.replace("{USER_ID}", f"\"..tostring(player.UserId)..\"")
				value = value.replace("{GUID}", f"\"..game:GetService(\"HttpService\"):GenerateGUID(false)..\"")
				dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", \"{value}\")"))
				dpath.new(type_tree, path, mark_as_literal("DataHandler<string, string>"))
		elif type(value) == bool:
			dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {value})"))
			dpath.new(type_tree, path, mark_as_literal("DataHandler<boolean, boolean>"))
		elif type(value) == int:
			dpath.new(func_tree, path, mark_as_literal(f"_newNumberHandler(\"{path}\", {value}, processors[\"int\"])"))
			dpath.new(type_tree, path, mark_as_literal("NumberDataHandler"))
		elif type(value) == float:
			dpath.new(func_tree, path, mark_as_literal(f"_newNumberHandler(\"{path}\", {value}, processors[\"float\"])"))
			dpath.new(type_tree, path, mark_as_literal("NumberDataHandler"))

	for path, value in dpath.search(config["types"], '**', yielded=True):
		
		if type(value) == str:
			if value[0:5] == "Enum.":
				enum_deserializers += write_enum_deserializer(value[5:])

	out_variable_content = []
	for k, v in out_variables.items():
		out_variable_content.append(f"local {k} = {v}")

	content = [
		"--!strict",
		HEADER_WARNING,
		"",
		"--Services",
		"local Players = game:GetService(\"Players\")",
		"local DataStoreService = game:GetService(\"DataStoreService\")",
		"local RunService = game:GetService(\"RunService\")",
		"local HttpService = game:GetService(\"HttpService\")",
		"",
		"--Packages",
		"local NetworkUtil = " + require_roblox_wally_package(NETWORK_UTIL_WALLY_PATH, is_header=False),
		"local Maid = " + require_roblox_wally_package(MAID_WALLY_PATH, is_header=False),
		"local Signal = " + require_roblox_wally_package(SIGNAL_WALLY_PATH, is_header=False),
		"",
		"--Modules",
		"local DataTypes = " + get_module_require(config["build"]["shared_types_roblox_path"]),
		"",
		"--Types",
		"type Signal = Signal.Signal",
		"type Maid = Maid.Maid",
		] + type_imports + [
		"export type UserId = number",
		"export type UserIdKey = string",
		"type Processor<V> = (val: V) -> V",
		"type Serializer<D,S> = (data: D) -> S",
		"type Deserializer<S,D> = (data: S) -> D",
		"export type DataHandler<T, S> = {",
		] + indent_block([
			"__index: DataHandler<T, S>,",
			"_Maid: Maid,",
			"_IsAlive: boolean,",
			"_Value: T?,",
			"_EncodedValue: S?,",
			"_Serialize: Serializer<T, S>,",
			"_Deserialize: Deserializer<S, T>,",
			"OnChanged: Signal,",
			"ClassName: \"DataHandler\",",
			"Key: UserIdKey,",
			"Player: Player,",
			"DataStore: DataStore,",
			"SetOptions: DataStoreSetOptions,",
			"IncrementOptions: DataStoreIncrementOptions,",
			"init: (maid: Maid) -> nil,",
			"new: (player: Player, scope: string, initialValue: T, serializer: Serializer<T,S>?, deserializer: Deserializer<S,T>?) -> DataHandler<T, S>,",
			"Destroy: (self: DataHandler<T, S>) -> nil,",
			"Get: (self: DataHandler<T, S>, force: boolean?) -> (T?, boolean),",
			"Set: (self: DataHandler<T, S>, data: T, force: boolean?) -> boolean,",
			"Update: (self: DataHandler<T, S>, transformer: (T) -> T, force: boolean?) -> (T?, boolean),",
			"Remove: (self: DataHandler<T, S>) -> nil,",
		]) + [
		"}",
		"export type SortedDataEntry = {",
		"\tUserId: number,",
		"\tValue: number,",
		"}",
		"export type NumberDataHandler = DataHandler<number, number> & {",
		] + indent_block([
			"ClassName: \"NumberDataHandler\",",
			"DataStore: OrderedDataStore,",
			"_EncodedValue: number?,",
			"_Serialize: Processor<number>,",
			"_Deserialize: Processor<number>,",
			"_Value: number?,",
			"Increment: (self: NumberDataHandler, delta: number, force: boolean?) -> (number?, boolean),",
			"new: (player: Player, scope: string, initialValue: number, processor: Processor<number>?) -> NumberDataHandler,",
			"GetSortedList: (self: NumberDataHandler, limit: number, isAscending: boolean) -> { [number]: SortedDataEntry },",
		]) + [
		"}",
		"export type DataTree = " + from_dict_to_type(type_tree, skip_initial_indent=True),
		"",
		"--Constants",
		"local BASE_DOMAIN = \"gamework\"",
		f"local GET_SUFFIX = \"{GET_SUFFIX_KEY}\"",
		f"local UPDATE_SUFFIX = \"{UPDATE_SUFFIX_KEY}\"",
		"local PAGE_LENGTH = 100",
		"local RETRY_LIMIT = if RunService:IsStudio() then 1 else 10",
		"local RETRY_DELAY = if RunService:IsStudio() then 0 else 0.5",
		"local METADATA = " + from_dict(config["metadata"]),
		"",
		"-- Private functions",
		"function serializeList(unitMethod: (val: any) -> string): ((val: {[number]: any}) -> string)",
		"	return function(dictVal: {[number]: any})",
		"		return \"{}\"",
		"	end",
		"end",
		"function deserializeList(unitMethod: (val: string) -> any): ((val: string) -> {[number]: any})",
		"	return function(dictVal: string)",
		"		return {}",
		"	end",
		"end",
		"function serializeDict(unitMethod: (val: any) -> string): ((val: {[string]: any}) -> string)",
		"	return function(dictVal: {[string]: any})",
		"		return \"{}\"",
		"	end",
		"end",
		"function deserializeDict(unitMethod: (val: string) -> any): ((val: string) -> {[string]: any})",
		"	return function(dictVal: string)",
		"		return {}",
		"	end",
		"end",
		""
		"local processors: {[string]: Processor<number>} = {}",
		"processors[\"Integer\"] = function(value: number): number",
		"\treturn math.round(value)",
		"end",
		"processors[\"int\"] = processors[\"Integer\"]",
		"processors[\"Double\"] = function(value: number): number",
		"\treturn math.round(value*100)/100",
		"end",
		"processors[\"double\"] = processors[\"Double\"]",
		"processors[\"Float\"] = function(value: number): number",
		"\treturn value",
		"end",
		"processors[\"float\"] = processors[\"Float\"]",
		"",
		"",
		"",
		"local serializers: {[string]: Serializer<any, any>} = {}",
		"serializers[\"Color3\"] = function(value: Color3): string",
		"\treturn value:ToHex()",
		"end",
		"serializers[\"number\"] = function(value: number): number",
		"\treturn value",
		"end",
		"serializers[\"string\"] = function(value: string): string",
		"\treturn value",
		"end",
		"serializers[\"boolean\"] = function(value: boolean): boolean",
		"\treturn value",
		"end",
		"serializers[\"DateTime\"] = function(value: DateTime): string",
		"\treturn value:ToIsoDate()",
		"end",
		"serializers[\"Vector3\"] = function(value: Vector3): string",
		] + indent_block([		
			"return HttpService:JSONEncode({",
			] + indent_block([	
				"X = value.X,",
				"Y = value.Y,",
				"Z = value.Z",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"Vector3Integer\"] = function(value: Vector3): string",
		] + indent_block([		
			"return HttpService:JSONEncode({",
			] + indent_block([	
				"X = math.round(value.X),",
				"Y = math.round(value.Y),",
				"Z = math.round(value.Z)",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"Vector3Double\"] = function(value: Vector3): string",
		] + indent_block([		
			"return HttpService:JSONEncode({",
			] + indent_block([	
				"X = math.round(value.X*100)/100,",
				"Y = math.round(value.Y*100)/100,",
				"Z = math.round(value.Z*100)/100",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"Vector2\"] = function(value: Vector2): string",
		] + indent_block([		
			"return HttpService:JSONEncode({",
			] + indent_block([	
				"X = value.X,",
				"Y = value.Y",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"Vector2Integer\"] = function(value: Vector2): string",
		] + indent_block([		
			"return HttpService:JSONEncode({",
			] + indent_block([	
				"X = math.round(value.X),",
				"Y = math.round(value.Y)",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"Vector2Double\"] = function(value: Vector2): string",
		] + indent_block([		
			"return HttpService:JSONEncode({",
			] + indent_block([	
				"X = math.round(value.X*100)/100,",
				"Y = math.round(value.Y*100)/100",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"CFrame\"] = function(value: CFrame): string",
		] + indent_block([		
			"local x,y,z = value:ToEulerAnglesYXZ()",
			"return HttpService:JSONEncode({",
			] + indent_block([
				"Position = serializers[\"Vector3\"](value.Position),",
				"Orientation = serializers[\"Vector3\"](Vector3.new(math.deg(x), math.deg(y), math.deg(z))),",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"CFrameDouble\"] = function(value: CFrame): string",
		] + indent_block([		
			"local x,y,z = value:ToEulerAnglesYXZ()",
			"return HttpService:JSONEncode({",
			] + indent_block([
				"Position = serializers[\"Vector3Double\"](value.Position),",
				"Orientation = serializers[\"Vector3Double\"](Vector3.new(math.deg(x), math.deg(y), math.deg(z))),",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"CFrameInteger\"] = function(value: CFrame): string",
		] + indent_block([		
			"local x,y,z = value:ToEulerAnglesYXZ()",
			"return HttpService:JSONEncode({",
			] + indent_block([
				"Position = serializers[\"Vector3Integer\"](value.Position),",
				"Orientation = serializers[\"Vector3Integer\"](Vector3.new(math.deg(x), math.deg(y), math.deg(z))),",
			]) + [
			"})",
		]) + [	
		"end",
		"serializers[\"Enum\"] = function(value: EnumItem): number",
		"\treturn value.Value",
		"end",
		] + type_serializers + [
		"",
		"",
		"",
		"local deserializers: {[string]: Deserializer<any, any>} = {}",
		"deserializers[\"string\"] = function(value: string): string",
		"\treturn value",
		"end",
		"deserializers[\"number\"] = function(value: number): number",
		"\treturn value",
		"end",
		"deserializers[\"boolean\"] = function(value: boolean): boolean",
		"\treturn value",
		"end",
		"deserializers[\"Color3\"] = function(value: string): Color3",
		"\treturn Color3.fromHex(value)",
		"end",
		"deserializers[\"DateTime\"] = function(value: string): DateTime",
		"\treturn DateTime.fromIsoDate(value)",
		"end",	
		"deserializers[\"Vector3\"] = function(value: string): Vector3",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"return Vector3.new(data.X, data.Y, data.Z)",
		]) + [	
		"end",
		"deserializers[\"Vector3Integer\"] = function(value: string): Vector3",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"return Vector3.new(math.round(data.X), math.round(data.Y), math.round(data.Z))",
		]) + [	
		"end",
		"deserializers[\"Vector3Double\"] = function(value: string): Vector3",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"return Vector3.new(math.round(data.X*100)/100, math.round(data.Y*100)/100, math.round(data.Z*100)/100)",
		]) + [	
		"end",
		"deserializers[\"Vector2\"] = function(value: string): Vector2",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"return Vector2.new(data.X, data.Y)",
		]) + [	
		"end",
		"deserializers[\"Vector2Integer\"] = function(value: string): Vector2",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"return Vector2.new(math.round(data.X), math.round(data.Y))",
		]) + [	
		"end",
		"deserializers[\"Vector2Double\"] = function(value: string): Vector2",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"return Vector2.new(math.round(data.X*100)/100, math.round(data.Y*100)/100)",
		]) + [	
		"end",
		"deserializers[\"CFrame\"] = function(value: string): CFrame",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"local position = deserializers[\"Vector3\"](data[\"Position\"])",
			"return CFrame.fromEulerAnglesYXZ(",
			"\tmath.rad(data.Orientation.X),",
			"\tmath.rad(data.Orientation.Y),",
			"\tmath.rad(data.Orientation.Z)",
			") + position"
		]) + [	
		"end",
		"deserializers[\"CFrameInteger\"] = function(value: string): CFrame",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"local position = deserializers[\"Vector3Integer\"](data[\"Position\"])",
			"return CFrame.fromEulerAnglesYXZ(",
			"\tmath.rad(math.round(data.Orientation.X)),",
			"\tmath.rad(math.round(data.Orientation.Y)),",
			"\tmath.rad(math.round(data.Orientation.Z))",
			") + position"
		]) + [	
		"end",
		"deserializers[\"CFrameDouble\"] = function(value: string): CFrame",
		] + indent_block([		
			"local data = HttpService:JSONDecode(value)",
			"local position = deserializers[\"Vector3Double\"](data[\"Position\"])",
			"return CFrame.fromEulerAnglesYXZ(",
			"\tmath.rad(math.round(data.Orientation.X*100)/100),",
			"\tmath.rad(math.round(data.Orientation.Y*100)/100),",
			"\tmath.rad(math.round(data.Orientation.Z*100)/100)",
			") + position"
		]) + [	
		"end",
		] + enum_deserializers + type_deserializers + [
		"",
		"--Class",
		"local DataHandler: DataHandler<any, string> = {} :: any",
		"DataHandler.__index = DataHandler",
		"",
		"function DataHandler:Destroy()",
		] + indent_block([	
			"if not self._IsAlive then",
			"\treturn",
			"end",
			"",
			"self._IsAlive = false",
			"self:Set(self._Value, true)",
			"self._Maid:Destroy()",
			"local t: any = self",
			"for k, v in pairs(t) do",
			"\tt[k] = nil",
			"end",
			"setmetatable(t, nil)",
			"return nil",
		]) + [	
		"end",
		"function DataHandler:Set(data: any, force: boolean?)",
		] + indent_block([	
			"local initialValue = self._EncodedValue",
			"local function set()",
			] + indent_block([	
				"local success, errorMessage = pcall(function()",
				"\tself.DataStore:SetAsync(self.Key, self._Serialize(data), { self.Player.UserId }, self.SetOptions)",
				"end)",
				"if not success then",
				"\twarn(errorMessage)",
				"end",
				"return success",
			]) + [	
			"end",
			"local success",	
			"if force then",
			] + indent_block([
				"local attempts = 0",
				"repeat",
				] + indent_block([
					"attempts += 1",
					"success = set()",
					"if not success then",
					"\ttask.wait(RETRY_DELAY)",
					"end",
				]) + [
				"until success or attempts > RETRY_LIMIT",
			]) + [
			"else",
			"\tsuccess = true",
			"end",
			"\tif data then",
			"\t\tself._EncodedValue = self._Serialize(data)",
			"\telse",
			"\t\tself._EncodedValue = nil",
			"\tend",
			"\tif self._EncodedValue then",
			"\t\tself._Value = self._Deserialize(self._EncodedValue)",
			"\telse",
			"\t\tself._Value = nil",
			"\tend",	
			"if initialValue ~= data then",
			"\tself.OnChanged:Fire(self._Value)",
			"end",
			"return success",
		]) + [
		"end",
		""
		"function DataHandler:Update(transformer: (any) -> any, force: boolean?)",
		] + indent_block([
			"local initialValue = self._EncodedValue",
			"local function transformerWrapper(rawValue: any)",
			"\t return self._Serialize(transformer(self._Deserialize(rawValue)))",
			"end",
			"local function update()",
			] + indent_block([	
				"local value = self._EncodedValue",
				"local success, msg = pcall(function()",
				"	value = self.DataStore:UpdateAsync(self.Key, transformerWrapper)",
				"end)",
				"if not success then",
				"	warn(msg)",
				"end",
				"return value, success",
			]) + [	
			"end",
			"",
			"local value, success",
			"if force then",
			] + indent_block([	
				"local attempts = 0",
				"repeat",
				] + indent_block([		
					"attempts += 1",
					"value, success = update()",
					"if not success then",
					"\ttask.wait(RETRY_DELAY)",
					"end",
				]) + [		
				"until success or attempts > RETRY_LIMIT",
				"if success then",
				"\tself._EncodedValue = value",
				"end",
			]) + [		
			"else",
			"\tvalue = transformerWrapper(initialValue)",
			"\tif value then",
			"\t\tself._EncodedValue = value",
			"\telse",
			"\t\tself._EncodedValue = nil",
			"\tend",
			"end",
			"\tif self._EncodedValue then",
			"\t\tself._Value = self._Deserialize(self._EncodedValue)",
			"\telse",
			"\t\tself._Value = nil",
			"\tend",	
			"if initialValue ~= value then",
			"\tself.OnChanged:Fire(self._Value)",
			"end",
			"return self._Value, success",
			]) + [
		"end",
		"",
		"function DataHandler:Get(force: boolean?): (any?, boolean)",
		] + indent_block([	
			"if self._Value ~= nil and not force then",
			"\treturn self._Value, true",
			"end",
			"",
			"local function get()",
				] + indent_block([		
					"local data",
					"local success, msg = pcall(function()",
					"\tdata = self.DataStore:GetAsync(self.Key)",
					"end)",
					"if not success then",
					"\twarn(msg)",
					"end",
					"return data, success",
				]) + [		
			"end",
			"",
			"local data, success",
			"local attempts = 0",
			"repeat",
			] + indent_block([			
				"attempts += 1",
				"data, success = get()",
				"if not success then",
				"\ttask.wait(RETRY_DELAY)",
				"end",
			]) + [	
			"until success or attempts > RETRY_LIMIT",
			"",
			"if success then",
			"\tself._EncodedValue = data",
			"\tif self._EncodedValue then",
			"\t\tself._Value = self._Deserialize(self._EncodedValue)",
			"\telse",
			"\t\tself._Value = nil",
			"\tend",
			"end",
			"",
			"return self._Value, success",
		]) + [
		"end",
		"",	
		"function DataHandler.new(player: Player, scope: string, initialValue: any, serializer: Serializer<any, string>?, deserializer: Deserializer<string, any>?)",
		] + indent_block([		
			"local maid = Maid.new()",
			"",
			"local dataStoreOptions = Instance.new(\"DataStoreOptions\")",
			"maid:GiveTask(dataStoreOptions)",
			"",
			"local setOptions = Instance.new(\"DataStoreSetOptions\")",
			"maid:GiveTask(setOptions)",
			"setOptions:SetMetadata(METADATA)",
			"",
			"local onChanged = Signal.new()",
			"maid:GiveTask(onChanged)",
			"",
			"local self: DataHandler<any, string> = setmetatable({",
			] + indent_block([		
				"_Maid = maid,",
				"_IsAlive = true,",
				"_Serialize = if serializer then serializer else function(v: any) return v end,",
				"_Deserialize = if deserializer then deserializer else function(v: any) return v end,",
				"OnChanged = onChanged,",
				"DataStore = if not RunService:IsStudio()",
				"\tthen DataStoreService:GetDataStore(BASE_DOMAIN, scope, dataStoreOptions)",
				"\telse nil :: any,",
				"_Value = initialValue,",
				"Key = tostring(player.UserId),",
				"SetOptions = setOptions,",
				"Player = player,",
			]) + [
			"}, DataHandler) :: any",
			"",
			"if RunService:IsRunning() then",
			] + indent_block([				
				"local updateEvent = NetworkUtil.getRemoteEvent(scope .. \"_\" .. UPDATE_SUFFIX, player)",
				"maid:GiveTask(updateEvent)",
				"",
				"maid:GiveTask(onChanged:Connect(function(v: any)",
				"\tupdateEvent:FireClient(player, v)",
				"end))",
				"",
				"local getFunction = NetworkUtil.getRemoteFunction(scope .. \"_\" .. GET_SUFFIX, player)",
				"maid:GiveTask(getFunction)",
				"getFunction.OnServerInvoke = function(plr: Player)",
				] + indent_block([	
					"if player.UserId == plr.UserId then",
					"\treturn self._Value",
					"end",
					"error(\"Bad player\")",
				]) + [
				"end",
			]) + [		
			"else",
			] + indent_block([			
				"local updateEvent = NetworkUtil.getBindableEvent(scope .. \"_\" .. UPDATE_SUFFIX)",
				"maid:GiveTask(updateEvent)",
				"",
				"maid:GiveTask(onChanged:Connect(function(v: any)",
				"\tupdateEvent:Fire(v)",
				"end))",
				"",
				"local getFunction = NetworkUtil.getBindableFunction(scope .. \"_\" .. GET_SUFFIX)",
				"maid:GiveTask(getFunction)",
				"getFunction.OnInvoke = function()",
				"\treturn self._Value",
				"end",
			]) + [		
			"end",
			"",
			"self._Value = self:Get(true)",
			"",
			"return self",
		]) + [
		"end",
		"",
		"local NumberDataHandler = {}",
		"NumberDataHandler.__index = NumberDataHandler",
		"setmetatable(NumberDataHandler, DataHandler)",
		"",
		"-- @TODO",
		"function NumberDataHandler:GetSortedList(player: Player, limit: number, isAscending: boolean)",
		] + indent_block([	
			"local pages = self.Datastore:GetSortedAsync(isAscending, PAGE_LENGTH)",
			"",
			"local list: { [number]: SortedDataEntry } = {}",
			"local function dumpPages()",
			] + indent_block([	
				"local page = pages:GetCurrentPage()",
				"",
				"for rank: number, data in ipairs(page) do",
				] + indent_block([	
					"if #list >= limit then",
					"\tbreak",
					"end",
					"local key = data.key",
					"local value = data.value",
					"table.insert(list, {",
					"\tUserId = tonumber(key) :: number,",
					"\tValue = value,",
				"})",
				]) + [	
			"end",
			"",
			"local success",
			"local attempts = 0",
			"repeat",
			] + indent_block([	
				"success = pcall(function() end)",
				"attempts += 1",
				"if not success then",
				"\ttask.wait(RETRY_DELAY)",
				"end",
			]) + [
			"until success or attempts > RETRY_LIMIT",
			"",
			"if success and #list < limit then",
			"\tpages:AdvanceToNextPageAsync()",
			"\tdumpPages()",
			"end",
		]) + [	
		"end",
		"dumpPages()",
		"",
		"return list",
		]) + [	
		"end",
		"",
		"function NumberDataHandler:Increment(delta: number, force: boolean?)",
			] + indent_block([	
			"local function increment()",
			] + indent_block([	
				"local value = self._EncodedValue",
				"local success, msg = pcall(function()",
				] + indent_block([	
					"local val = self.DataStore:IncrementAsync(self.Key, delta, { self.Player.UserId }, self.IncrementOptions)",
					"value = val",
					"return val",
				]) + [
				"end)",
				"if not success then",
				"\twarn(msg)",
				"end",
				"return value, success",
			]) + [
			"end",
			"",
			"local value, success",
			"",
			"if force then",
			] + indent_block([	
				"local attempts = 0",
				"repeat",
				] + indent_block([	
					"attempts += 1",
					"value, success = increment()",
					"if not success then",
					"\ttask.wait(RETRY_DELAY)",
					"end",
				]) + [
				"until success or attempts > RETRY_LIMIT",
				"if success then",
				"\tself._EncodedValue = value",
				"\tself._Value = self.Deserialize(self._EncodedValue)"
				"end"
			]) + [
			"else",
			] + indent_block([	
				"local val: number = self._EncodedValue",
				"val += delta",
				"self._EncodedValue = val",
				"self._Value = self.Deserialize(self._EncodedValue)",
				"success = true",
			]) + [
			"end",
			"",
			"if success and delta ~= 0 then",
			"\tself.OnChanged:Fire(self._Value)",
			"end",
			"",
			"return self._Value, success",
		]) + [	
		"end",
		"",
		"function NumberDataHandler.new(player: Player, scope: string, initialValue: number, processor: Processor<number>?): NumberDataHandler",
		] + indent_block([	
			"local self: NumberDataHandler = setmetatable(DataHandler.new(player, scope, initialValue, processor :: any, processor :: any), NumberDataHandler) :: any",
			"",
			"self.DataStore = if not RunService:IsStudio()",
			"\tthen DataStoreService:GetOrderedDataStore(BASE_DOMAIN, scope)",
			"\telse nil :: any",
			"",
			"local incrementOptions = Instance.new(\"DataStoreIncrementOptions\")",
			"self._Maid:GiveTask(incrementOptions)",
			"",
			"incrementOptions:SetMetadata(METADATA)",
			"self.IncrementOptions = incrementOptions",
			"",
			"return self",
		]) + [	
		"end",
		"local trees: { [number]: any } = {}",
		"",
		"function initPlayer(playerMaid: Maid, player: Player)",
		] + indent_block([	
			"local function _newDataHandler<G, S>(path: string, val: any, serializer: Serializer<G,S>?, deserializer: Deserializer<S, G>?): DataHandler<G, S>",
			] + indent_block([	
				"local handler: DataHandler<G,S> = DataHandler.new(player, path, val, serializer :: any, deserializer :: any) :: any",
				"playerMaid:GiveTask(handler)",
				"",
				"return handler",
			]) + [
			"end",
			"",
			"local function _newNumberHandler(path: string, val: number, processor: Processor<number>?): NumberDataHandler",
			] + indent_block([	
				"local handler: NumberDataHandler = NumberDataHandler.new(player, path, val, processor) :: any",
				"playerMaid:GiveTask(handler)",
				"",
				"return handler",
			]) + [
			"end",
			"",
			] + out_variable_content + [
			"local tree: DataTree = " + from_dict(func_tree, indent_count=2, add_comma_at_end=False, skip_initial_indent=True),
			"trees[player.UserId] = tree",
		]) + [
		"end",
		"",
		"return {",
		] + indent_block([	
			"init = function(maid: Maid): nil",
			] + indent_block([	
				"local function onPlayerAdded(player: Player)",
				] + indent_block([	
				"local playerMaid = Maid.new()",
				"maid:GiveTask(playerMaid)",
				"initPlayer(playerMaid, player)",
				"playerMaid:GiveTask(player.Destroying:Connect(function()",
				"\ttrees[player.UserId] = nil",
				"\tplayerMaid:Destroy()",
				"end))",
				]) + [
				"end",
				"",
				"maid:GiveTask(Players.PlayerAdded:Connect(onPlayerAdded))",
				"for i, player in ipairs(game.Players:GetChildren()) do",
				"\tonPlayerAdded(player)",
				"end",
				"",
				"return nil",
			]) + [
			"end,",
			"get = function(userId: number, yieldDuration: number?): DataTree?",
			] + indent_block([	
				"local function get()",
				"\treturn trees[userId]",
				"end",
				"local tree = get()",
				"if not tree and yieldDuration then",
				] + indent_block([	
					"local start = tick()",
					"repeat",
					"\ttask.wait()",
					"\ttree = get()",
					"until tree or tick() - start > yieldDuration",
					"return tree",
				]) + [
				"else",
				"\treturn tree",
				"end",
			]) + [
			"end,",
		]) + [
		"}",
	]
	write_script(build_path, "\n".join(content), write_as_directory=False)

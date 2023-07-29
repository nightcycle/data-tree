import dpath
from src.util import get_package_zip_path, get_if_optional, write_value_from_config, write_standard_value_from_config, get_raw_key_name, get_type_name_from_key, get_roblox_type, get_raw_type_name
from luau import indent_block
from luau.convert import from_dict, mark_as_literal, from_dict_to_type, from_list
from luau.roblox import write_script, get_package_require
from luau.roblox.util import get_module_require
from luau.path import get_if_module_script, remove_all_path_variants
from src.config import get_data_config, SIGNAL_WALLY_PATH, NETWORK_UTIL_WALLY_PATH, MAID_WALLY_PATH, HEADER_WARNING, GET_SUFFIX_KEY, UPDATE_SUFFIX_KEY
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

def get_function_name(text: str) -> str:
	first_char = text[0].upper()
	return (first_char + text[1:]).replace("Enum.", "Enum")


def build():
	config = get_data_config()

	build_path = config["build"]["out"]["server_path"]
	assert get_if_module_script(build_path), "server datatree must be a ModuleScript, please make sure the server_path only ends with .lua/luau"

	remove_all_path_variants(build_path)

	type_imports = []
	for key in config["types"]:
		type_imports.append(f"export type {key} = DataTypes.{key}")


	enum_str_list = []
	for path, value in dpath.search(config["types"], '**', yielded=True):
		if "Enum." in value:
			enum_str_list.append(value)

	# State::Enum.HumanoidStateType
	for path, value in dpath.search(config["tree"], '**', yielded=True):
		if ("Enum." in path) and ("::" in path):
			enum_str_list.append(path.split("::")[1])

	type_tree = {}
	func_tree = {}
	enum_deserializers = []
	type_serializers = []
	type_deserializers = []

	def assemble_serializer_function(type_name: str, type_data: dict | list) -> list[str]:

		if type(type_data) == dict:
			_serializer_content = [
				f"local _serialize{get_function_name(type_name)} = function(value: {type_name}): Table",
			]
			out: dict = {}
			for path, value in dpath.search(type_data, '**', yielded=True):
				if type(value) == str:
					keys = path.split("/")
					key_str = "value"
					is_optional = "?" == value[len(value)-1]
					for key in keys:
						key_str += "[\""+key+"\"]"
					if value in config["types"]:
						if is_optional:
							dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _serialize{get_function_name(value)}({key_str}) else nil"))
						else:
							dpath.new(out, path, mark_as_literal(f"_serialize{get_function_name(value)}({key_str})"))
					else:
						if "List[" in value:
							true_type_name = value.replace("List[", "").replace("]", "")
							if true_type_name[0] == " ":
								true_type_name = true_type_name[1:]
							if is_optional:
								dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _serializeList(_serialize{get_function_name(true_type_name)})({key_str}) else nil"))
							else:
								dpath.new(out, path, mark_as_literal(f"_serializeList(_serialize{get_function_name(true_type_name)})({key_str})"))
						elif "Dict[" in value:
							true_type_name = value.replace("Dict[", "").replace("]", "").split(",")[1]
							if true_type_name[0] == " ":
								true_type_name = true_type_name[1:]
							if is_optional:
								dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _serializeDict(_serialize{get_function_name(true_type_name)})({key_str}) else nil"))
							else:
								dpath.new(out, path, mark_as_literal(f"_serializeDict(_serialize{get_function_name(true_type_name)})({key_str})"))
						else:
							ro_type = get_roblox_type(get_raw_type_name(value))
							if ro_type != None:
								assert ro_type
								if is_optional:
									dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _serialize{get_function_name(ro_type)}({key_str}) else nil"))
								else:
									dpath.new(out, path, mark_as_literal(f"_serialize{get_function_name(value)}({key_str})"))
				
			_serializer_content += indent_block(("return " + from_dict(out, skip_initial_indent=True) + "").split("\n"))
			_serializer_content.append("end")

			return _serializer_content
		elif type(type_data) == list:
			_serializer_content = [
				f"local _serialize{get_function_name(type_name)} = function(value: {type_name}): string",
				f"\tlocal index = table.find({from_list(type_data, indent_count=0, multi_line=False, skip_initial_indent=True)}, value)",
				"\tassert(index)",
				"\treturn tostring(index)",
				"end",
			]

			return _serializer_content

		return []

	def assemble_deserializer_function(type_name: str, type_data: dict | list) -> list[str]:
		if type(type_data) == dict:
			_deserializer_content = [
				f"local _deserialize{get_function_name(type_name)} = function(data: Table): {type_name}",
			]
			out: dict = {}
			for path, value in dpath.search(type_data, '**', yielded=True):
				if type(value) == str:
					keys = path.split("/")
					key_str = "data"
					is_optional = "?" == value[len(value)-1]
					for key in keys:
						key_str += "[\""+key+"\"]"
					if value in config["types"]:
						if is_optional:
							dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _deserialize{get_function_name(value)}({key_str}) else nil"))
						else:
							dpath.new(out, path, mark_as_literal(f"_deserialize{get_function_name(value)}({key_str})"))
					else:
						if "List[" in value:
							true_type_name = value.replace("List[", "").replace("]", "")
							if true_type_name[0] == " ":
								true_type_name = true_type_name[1:]
							if is_optional:	
								dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _deserializeList(_deserialize{get_function_name(true_type_name)})({key_str}) else nil"))
							else:
								dpath.new(out, path, mark_as_literal(f"_deserializeList(_deserialize{get_function_name(true_type_name)})({key_str})"))
						elif "Dict[" in value:
							true_type_name = value.replace("Dict[", "").replace("]", "").split(",")[1]
							if true_type_name[0] == " ":
								true_type_name = true_type_name[1:]
							if is_optional:	
								dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _deserializeDict(_deserialize{get_function_name(true_type_name)})({key_str}) else nil"))
							else:
								dpath.new(out, path, mark_as_literal(f"_deserializeDict(_deserialize{get_function_name(true_type_name)})({key_str})"))
						else:
							ro_type = get_roblox_type(get_raw_type_name(value))
							if ro_type != None:
								assert ro_type
								if is_optional:
									dpath.new(out, path, mark_as_literal(f"if {key_str} ~= nil then _deserialize{get_function_name(ro_type)}({key_str}) else nil"))
								else:
									dpath.new(out, path, mark_as_literal(f"_deserialize{get_function_name(ro_type)}({key_str})"))

			_deserializer_content += indent_block(("return " + from_dict(out, skip_initial_indent=True) + " :: any").split("\n"))
			_deserializer_content.append("end")

			return _deserializer_content
		elif type(type_data) == list:
			_deserializer_content = [
				f"local _deserialize{get_function_name(type_name)} = function(value: number): {type_name}",
				f"\tlocal options = {from_list(type_data, indent_count=0, multi_line=False, skip_initial_indent=True)}",
				f"\tlocal index = tonumber(value)",
				f"\tassert(index)",
				f"\treturn options[index] :: {type_name}",
				"end",
			]

			return _deserializer_content
		return []

	for enum_type in enum_str_list:
		type_serializers += [
			f"local _serialize{get_function_name(enum_type)} = _serializeEnum :: (value: {enum_type}) -> string",
		]

	for type_name, type_data in config["types"].items():
		type_deserializers += assemble_deserializer_function(type_name, type_data)
		type_serializers += assemble_serializer_function(type_name, type_data)

	def write_enum_deserializer(enum_name: str):
		raw_enum_name = get_raw_type_name(enum_name)
		enum_func_name = get_function_name("Enum."+raw_enum_name)
		return [
			f"local _deserialize{enum_func_name} = function(value: string): Enum.{raw_enum_name}",
			f"\tfor i, enumItem in ipairs(Enum.{raw_enum_name}:GetEnumItems()) do if enumItem.Value == tonumber(value) then return enumItem end end",
			f"\terror(\"No enum item found in {raw_enum_name} for value \"..value)",
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
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, _serialize{get_function_name(final_type)}, _deserialize{get_function_name(final_type)})"))
				else:
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, _serialize{get_function_name(final_type)}, _deserialize{get_function_name(final_type)})"))

				dpath.new(type_tree, path, mark_as_literal(f"DataHandler<{final_type}, string>"))
			elif final_type[0:5] == "List[":
				if not get_if_number_in_path(full_path):
					initial_value = write_value_from_config(value, final_type, config["types"])
					inner_type = final_type[5:(len(final_type)-1)]
					raw_inner_type = get_raw_type_name(inner_type)
					out_variables[typed_var_name] = initial_value

					if raw_inner_type[0] == " ":
						raw_inner_type = raw_inner_type[1:]

					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, _serializeList(_serialize{get_function_name(raw_inner_type)}), _deserializeList(_deserialize{get_function_name(raw_inner_type)})) :: any"))
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

					if raw_val[0] == " ":
						raw_val = raw_val[1:]

					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", {var_name}, _serializeDict(_serialize{get_function_name(raw_val)}), _deserializeDict(_deserialize{get_function_name(raw_val)})) :: any"))
					dpath.new(type_tree, path, mark_as_literal("DataHandler<{["+key+"]: "+val+"}, string>"))
			else:
				ro_type = get_roblox_type(final_type)
				if ro_type == "number":
					dpath.new(func_tree, path, mark_as_literal(f"_newNumberHandler(\"{path}\", {value}, _process{get_function_name(final_type)})"))
					dpath.new(type_tree, path, mark_as_literal("NumberDataHandler"))
				else:
					dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\")"))
					dpath.new(type_tree, path, mark_as_literal(f"DataHandler<{ro_type}, string>"))
		
		elif type(value) == str:
			raw_value = get_raw_type_name(value)
			if raw_value in config["types"]:
				dpath.new(func_tree, path, mark_as_literal(f"_newDataHandler(\"{path}\", nil, _serialize{raw_value}, _deserialize{raw_value})"))
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
			dpath.new(func_tree, path, mark_as_literal(f"_newNumberHandler(\"{path}\", {value}, _processInt\"])"))
			dpath.new(type_tree, path, mark_as_literal("NumberDataHandler"))
		elif type(value) == float:
			dpath.new(func_tree, path, mark_as_literal(f"_newNumberHandler(\"{path}\", {value}, _processFloat\"])"))
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
		"local DataStoreService = " + get_package_require("MockDataStoreService"),
		"local RunService = game:GetService(\"RunService\")",
		"local HttpService = game:GetService(\"HttpService\")",
		"",
		"--Packages",
		"local NetworkUtil = " + get_package_require("NetworkUtil"),
		"local Maid = " + get_package_require("Maid"),
		"local Signal = " + get_package_require("Signal"),
		"local Base64 = " + get_package_require("Base64"),
		"",
		"--Modules",
		"local DataTypes = " + get_module_require(config["build"]["shared_types_roblox_path"]),
		"",
		"--Types",
		"type Table = {[any]: any}",
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
			"new: (player: Player, scope: string, initialValue: T, _serializer: Serializer<T,S>?, _deserializer: Deserializer<S,T>?) -> DataHandler<T, S>,",
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
			"new: (player: Player, scope: string, initialValue: number, _processor: Processor<number>?) -> NumberDataHandler,",
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
		"local RETRY_LIMIT = 10",
		"local RETRY_DELAY = 0.5",
		"local METADATA = " + from_dict(config["metadata"]),
		"",
		"-- Private functions",
		"function _serializeList(unitMethod: (((val: any) -> Table) | ((val: any) -> string) | ((val: number) -> number) | ((val: boolean) -> boolean))): (val: { [number]: any }) -> Table",
		"	return function(listVal: { [number]: any }): Table",
		"		local out = {}",
		"		for i, v in ipairs(listVal) do",
		"			out[i] = (unitMethod :: any)(v)",
		"		end",
		"		return out",
		"	end",
		"end",
		"function _deserializeList(unitMethod: (((val: string) -> any) | ((val: Table) -> any) | ((val: number) -> number) | ((val: boolean) -> boolean))): (input: {[number]: any}) -> { [number]: any }",
		"	return function(input: Table)",
		"		local out = {}",
		"		for i, v in ipairs(input) do",
		"			out[i] = (unitMethod :: any)(v)",
		"		end",
		"		return out",
		"	end",
		"end",
		"function _serializeDict(unitMethod: (((val: any) -> Table) | ((val: any) -> string) | ((val: number) -> number) | ((val: boolean) -> boolean))): (val: { [any]: any }) -> Table",
		"	return function(dictVal: { [any]: any }): Table",
		"		local out = {}",
		"		for k, v in pairs(dictVal) do",
		"			out[k] = (unitMethod :: any)(v)",
		"		end",
		"		return out",
		"	end",
		"end",
		"function _deserializeDict(unitMethod: (((val: string) -> any) | ((val: Table) -> any) | ((val: number) -> number) | ((val: boolean) -> boolean))): (val: Table) -> { [any]: any }",
		"	return function(input: Table): { [any]: any }",
		"		local out = {}",
		"		for k, v in pairs(input) do",
		"			out[k] = (unitMethod :: any)(v)",
		"		end",
		"		return out",
		"	end",
		"end",
		"",
		"local _processInteger = function(value: number): number",
		"\treturn math.round(value)",
		"end",
		"local _processInt = _processInteger",
		"local _processDouble = function(value: number): number",
		"\treturn math.round(value*100)/100",
		"end",
		"local _processFloat = function(value: number): number",
		"\treturn value",
		"end",
		"",
		"",
		"",
		"local _serializeColor3 = function(value: Color3): string",
		"\treturn value:ToHex()",
		"end",
		"local _serializeNumber = function(value: number): number",
		"\treturn value",
		"end",
		"local _serializeInteger = function(value: number): number",
		"\treturn _processInteger(value)",
		"end",
		"local _serializeInt = _serializeInteger",
		"local _serializeDouble = function(value: number): number",
		"\treturn _processDouble(value)",
		"end",
		"local _serializeFloat = _serializeNumber",
		"local _serializeString = function(value: string): string",
		"\treturn value",
		"end",
		"local _serializeBoolean = function(value: boolean): boolean",
		"\treturn value",
		"end",
		"local _serializeDateTime = function(value: DateTime): string",
		"\treturn value:ToIsoDate()",
		"end",
		"local _serializeVector3 = function(value: Vector3): Table",
		] + indent_block([		
			"return {",
			] + indent_block([	
				"X = value.X,",
				"Y = value.Y,",
				"Z = value.Z",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeVector3Integer = function(value: Vector3): Table",
		] + indent_block([		
			"return {",
			] + indent_block([	
				"X = math.round(value.X),",
				"Y = math.round(value.Y),",
				"Z = math.round(value.Z)",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeVector3Double = function(value: Vector3): Table",
		] + indent_block([		
			"return {",
			] + indent_block([	
				"X = math.round(value.X*100)/100,",
				"Y = math.round(value.Y*100)/100,",
				"Z = math.round(value.Z*100)/100",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeVector2 = function(value: Vector2): Table",
		] + indent_block([		
			"return {",
			] + indent_block([	
				"X = value.X,",
				"Y = value.Y",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeVector2Integer = function(value: Vector2): Table",
		] + indent_block([		
			"return {",
			] + indent_block([	
				"X = math.round(value.X),",
				"Y = math.round(value.Y)",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeVector2Double = function(value: Vector2): Table",
		] + indent_block([		
			"return {",
			] + indent_block([	
				"X = math.round(value.X*100)/100,",
				"Y = math.round(value.Y*100)/100",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeCFrame = function(value: CFrame): Table",
		] + indent_block([		
			"local x,y,z = value:ToEulerAnglesYXZ()",
			"return {",
			] + indent_block([
				"Position = _serializeVector3(value.Position),",
				"Orientation = _serializeVector3(Vector3.new(math.deg(x), math.deg(y), math.deg(z))),",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeCFrameDouble = function(value: CFrame): Table",
		] + indent_block([		
			"local x,y,z = value:ToEulerAnglesYXZ()",
			"return {",
			] + indent_block([
				"Position = _serializeVector3Double(value.Position),",
				"Orientation = _serializeVector3Double(Vector3.new(math.deg(x), math.deg(y), math.deg(z))),",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeCFrameInteger = function(value: CFrame): Table",
		] + indent_block([		
			"local x,y,z = value:ToEulerAnglesYXZ()",
			"return {",
			] + indent_block([
				"Position = _serializeVector3Integer(value.Position),",
				"Orientation = _serializeVector3Integer(Vector3.new(math.deg(x), math.deg(y), math.deg(z))),",
			]) + [
			"}",
		]) + [	
		"end",
		"local _serializeEnum = function(value: EnumItem): string",
		"\treturn tostring(value.Value)",
		"end",
		] + type_serializers + [
		"",
		"",
		"",
		"local _deserializeString = function(value: string): string",
		"\treturn value",
		"end",
		"local _deserializeNumber = function(value: number): number",
		"\treturn value",
		"end",
		"local _deserializeInteger = _deserializeNumber",
		"local _deserializeInt = _deserializeInteger",
		"local _deserializeDouble = _deserializeNumber",
		"local _deserializeFloat = _deserializeNumber",
		"local _deserializeBoolean = function(value: boolean): boolean",
		"\treturn value",
		"end",
		"local _deserializeColor3 = function(value: string): Color3",
		"\treturn Color3.fromHex(value)",
		"end",
		"local _deserializeDateTime = function(value: string): DateTime",
		"\treturn DateTime.fromIsoDate(value)",
		"end",	
		"local _deserializeVector3 = function(value: Table): Vector3",
		] + indent_block([		
			"return Vector3.new(value.X, value.Y, value.Z)",
		]) + [	
		"end",
		"local _deserializeVector3Integer = function(value: Table): Vector3",
		] + indent_block([		
			"return Vector3.new(math.round(value.X), math.round(value.Y), math.round(value.Z))",
		]) + [	
		"end",
		"local _deserializeVector3Double = function(value: Table): Vector3",
		] + indent_block([		
			"return Vector3.new(math.round(value.X*100)/100, math.round(value.Y*100)/100, math.round(value.Z*100)/100)",
		]) + [	
		"end",
		"local _deserializeVector2 = function(value: Table): Vector2",
		] + indent_block([		
			"return Vector2.new(value.X, value.Y)",
		]) + [	
		"end",
		"local _deserializeVector2Integer = function(value: Table): Vector2",
		] + indent_block([		
			"return Vector2.new(math.round(value.X), math.round(value.Y))",
		]) + [	
		"end",
		"local _deserializeVector2Double = function(value: Table): Vector2",
		] + indent_block([		
			"return Vector2.new(math.round(value.X*100)/100, math.round(value.Y*100)/100)",
		]) + [	
		"end",
		"local _deserializeCFrame = function(value: Table): CFrame",
		] + indent_block([		
			"local position = _deserializeVector3(value[\"Position\"])",
			"local orientation = _deserializeVector3(value[\"Orientation\"])",
			"return CFrame.fromEulerAnglesYXZ(",
			"\tmath.rad(orientation.X),",
			"\tmath.rad(orientation.Y),",
			"\tmath.rad(orientation.Z)",
			") + position"
		]) + [	
		"end",
		"local _deserializeCFrameInteger = function(value: Table): CFrame",
		] + indent_block([		
			"local position = _deserializeVector3Integer(value[\"Position\"])",
			"local orientation = _deserializeVector3Integer(value[\"Orientation\"])",
			"return CFrame.fromEulerAnglesYXZ(",
			"\tmath.rad(orientation.X),",
			"\tmath.rad(orientation.Y),",
			"\tmath.rad(orientation.Z)",
			") + position"
		]) + [	
		"end",
		"local _deserializeCFrameDouble = function(value: Table): CFrame",
		] + indent_block([		
			"local position = _deserializeVector3Double(value[\"Position\"])",
			"local orientation = _deserializeVector3Double(value[\"Orientation\"])",
			"return CFrame.fromEulerAnglesYXZ(",
			"\tmath.rad(orientation.X),",
			"\tmath.rad(orientation.Y),",
			"\tmath.rad(orientation.Z)",
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
			] + indent_block([
				] + indent_block([
					"if type(data) == \"string\" then",
					"\tself._EncodedValue = self._Serialize(data) -- Base64.Encode(self._Serialize(data))",
					"else",
					"\tself._EncodedValue = self._Serialize(data)",
					"end",
				]) + [
			]) + [
			"\telse",
			"\t\tself._EncodedValue = nil",
			"\tend",
			"\tif self._EncodedValue then",
			] + indent_block([
				] + indent_block([
					"if type(self._EncodedValue) == \"string\" then",
					"\tself._Value = self._Deserialize(self._EncodedValue) -- self._Deserialize(Base64.Decode(self._EncodedValue))",
					"else",
					"\t\tself._Value = self._Deserialize(self._EncodedValue)",
					"end",
				]) + [
			]) + [
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
			] + indent_block([
				] + indent_block([
					"if type(value) == \"string\" then",
					"\tself._EncodedValue = self._Serialize(value) -- Base64.Encode(self._Serialize(value))",
					"else",
					"\tself._EncodedValue = self._Serialize(value)",
					"end",
				]) + [
			]) + [
			"\telse",
			"\t\tself._EncodedValue = nil",
			"\tend",
			"end",
			"\tif self._EncodedValue then",
			] + indent_block([
				] + indent_block([
					"if type(self._EncodedValue) == \"string\" then",
					"\tself._Value = self._Deserialize(self._EncodedValue) -- self._Deserialize(Base64.Decode(self._EncodedValue))",
					"else",
					"\t\tself._Value = self._Deserialize(self._EncodedValue)",
					"end",
				]) + [
			]) + [
			
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
			] + indent_block([
				] + indent_block([
					"if type(self._EncodedValue) == \"string\" then",
					"\tself._Value = self._Deserialize(self._EncodedValue) -- self._Deserialize(Base64.Decode(self._EncodedValue))",
					"else",
					"\t\tself._Value = self._Deserialize(self._EncodedValue)",
					"end",
				]) + [
			]) + [
			"\telse",
			"\t\tself._Value = nil",
			"\tend",
			"end",
			"",
			"return self._Value, success",
		]) + [
		"end",
		"",	
		"function DataHandler.new(player: Player, scope: string, initialValue: any, _serializer: Serializer<any, any>?, _deserializer: Deserializer<any, any>?)",
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
				"_Serialize = if _serializer then",
				"\tfunction(v: any)",
				"\t\treturn if type(v) == \"table\" then Base64.Encode(HttpService:JSONEncode(_serializer(v))) else v",
				"\tend",
				"else function(v: any) return v end,",
				"_Deserialize = if _deserializer then ",
				"\tfunction(v: any)",
				"\t\tlocal out: any",
				"\t\tlocal success, _msg = pcall(function()",
				"\t\t\tout = _deserializer(HttpService:JSONDecode(Base64.Decode(v)))",
				"\t\tend)",
				"\t\treturn if success then out else v"
				"\tend",
				"else function(v: any) return v end,",
				# "_Serialize = if _serializer then _serializer else function(v: any) return v end,",
				# "_Deserialize = if _deserializer then _deserializer else function(v: any) return v end,",
				"OnChanged = onChanged,",
				"DataStore =  DataStoreService:GetDataStore(BASE_DOMAIN, scope, dataStoreOptions),",
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
			"if self._Value == nil then self._Value = initialValue end",
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
		"function NumberDataHandler.new(player: Player, scope: string, initialValue: number, _processor: Processor<number>?): NumberDataHandler",
		] + indent_block([	
			"local self: NumberDataHandler = setmetatable(DataHandler.new(player, scope, initialValue, _processor :: any, _processor :: any), NumberDataHandler) :: any",
			"",
			"self.DataStore = DataStoreService:GetOrderedDataStore(BASE_DOMAIN, scope)",
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
			"local function _newDataHandler<G, S>(path: string, val: any, _serializer: Serializer<G,S>?, _deserializer: Deserializer<S, G>?): DataHandler<G, S>",
			] + indent_block([	
				"local handler: DataHandler<G,S> = DataHandler.new(player, path, val, _serializer :: any, _deserializer :: any) :: any",
				"playerMaid:GiveTask(handler)",
				"",
				"return handler",
			]) + [
			"end",
			"",
			"local function _newNumberHandler(path: string, val: number, _processor: Processor<number>?): NumberDataHandler",
			] + indent_block([	
				"local handler: NumberDataHandler = NumberDataHandler.new(player, path, val, _processor) :: any",
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
				"for i, player in ipairs(Players:GetChildren()) do",
				"\tonPlayerAdded(player :: Player)",
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
	write_script(build_path, "\n".join(content), packages_dir_zip_file_path=get_package_zip_path(), skip_source_map=True)

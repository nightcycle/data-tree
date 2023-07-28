import dpath
from src.util import get_raw_type_name, get_raw_key_name, get_type_name_from_key, get_roblox_type, get_package_zip_path
from luau import indent_block
from luau.convert import from_dict, mark_as_literal, from_dict_to_type
from luau.roblox import write_script, get_package_require
from luau.roblox.util import get_module_require
from luau.path import get_if_module_script, remove_all_path_variants
from src.config import get_data_config, HEADER_WARNING, GET_SUFFIX_KEY, UPDATE_SUFFIX_KEY

def build() -> None:
	config = get_data_config()

	build_path = config["build"]["out"]["client_path"]
	assert get_if_module_script(build_path), "client datatree must be a ModuleScript, please make sure the client_path only ends with .lua/luau"
	assert not "init" in config["tree"], "\"init\" is reserved for a funciton in the client tree type."
	
	remove_all_path_variants(build_path)
	
	type_imports = []
	for key in config["types"]:
		type_imports.append(f"export type {key} = DataTypes.{key}")

	type_tree: dict = {}
	func_tree: dict = {}
	for full_path, value in dpath.search(config["tree"], '**', yielded=True):
		keys = full_path.split("/")
		raw_keys = []
		final_type: None | str = None
		for key in keys:
			if final_type == None:
				raw_keys.append(get_raw_key_name(key))
				final_type = get_type_name_from_key(key)
						

		path = "/".join(raw_keys)
		if len(raw_keys) < len(keys):
			ro_type = get_roblox_type(final_type)
			dpath.new(func_tree, path, mark_as_literal(f"newReceiver(\"{path}\")"))
			dpath.new(type_tree, path, mark_as_literal(f"Receiver<{ro_type}>"))
		elif type(value) == str:
			raw_value = get_raw_type_name(value)
			if raw_value in config["types"]:
				dpath.new(func_tree, path, mark_as_literal(f"newReceiver(\"{path}\")"))
				dpath.new(type_tree, path, mark_as_literal(f"Receiver<{final_type}>"))
			else:
				dpath.new(func_tree, path, mark_as_literal(f"newReceiver(\"{path}\")"))
				dpath.new(type_tree, path, mark_as_literal("Receiver<string>"))
		elif type(value) == bool:
			dpath.new(func_tree, path, mark_as_literal(f"newReceiver(\"{path}\")"))
			dpath.new(type_tree, path, mark_as_literal("Receiver<boolean>"))
		elif type(value) == int or type(value) == float:
			dpath.new(func_tree, path, mark_as_literal(f"newReceiver(\"{path}\")"))
			dpath.new(type_tree, path, mark_as_literal("Receiver<number>"))

	type_tree["init"] = mark_as_literal("(maid: Maid) -> nil")
	func_tree["init"] = mark_as_literal("function(maid: Maid) return nil end")
	content = [
		"--!strict",
		HEADER_WARNING,
		"",
		"--Services",
		"local RunService = game:GetService(\"RunService\")",
		"local Players = game:GetService(\"Players\")",
		"",
		"--Packages",
		"local NetworkUtil = " + get_package_require("NetworkUtil"),
		"local Maid = " + get_package_require("Maid"),
		"local ServiceProxy = " + get_package_require("ServiceProxy"),
		"",
		"--Modules",
		"local DataTypes = " + get_module_require(config["build"]["shared_types_roblox_path"]),
		"",
		"--Types",
		"type Maid = Maid.Maid",
		"export type Receiver<T> = () -> T",
	] + type_imports + [
		"",
		"export type DataTree = " + from_dict_to_type(type_tree),
		"",
		"--Constants",
		f"local GET_SUFFIX = \"{GET_SUFFIX_KEY}\"",
		f"local UPDATE_SUFFIX = \"{UPDATE_SUFFIX_KEY}\"",
		"",
		"-- Class",
		"local tree: DataTree = {} :: any",
		"local values = {}",
		"function tree.init(maid: Maid): nil",
		"	local function newReceiver<T>(scope: string): Receiver<T>",
		"		local updateKey = scope .. \"_\" .. UPDATE_SUFFIX",
		"		local getKey = scope .. \"_\" .. GET_SUFFIX",
		"",
		"		if RunService:IsRunning() then",
		"			maid:GiveTask(NetworkUtil.onClientEventAt(updateKey, Players.LocalPlayer, function(val)",
		"				values[scope] = val",
		"			end))",
		"			values[scope] = NetworkUtil.invokeServerAt(getKey, Players.LocalPlayer)",
		"		else",
		"			local bindableEvent = NetworkUtil.getBindableEvent(updateKey)",
		"			maid:GiveTask(bindableEvent.Event:Connect(function(val)",
		"				values[scope] = val",
		"			end))",
		"			local bindableFunction = NetworkUtil.getBindableFunction(getKey)",
		"			values[scope] = bindableFunction:Invoke()",
		"		end",
		"",
		"		return function(): T",
		"			return values[scope] :: any",
		"		end",
		"	end",
		"",
		"	tree = " + from_dict(func_tree, indent_count=1, skip_initial_indent=True),
		"	return nil",
		"end",
		"",
		"return ServiceProxy(function()",
		"\treturn tree",
		"end)"

	]
	write_script(build_path, "\n".join(content), packages_dir_zip_file_path=get_package_zip_path(), skip_source_map=True)
	return None

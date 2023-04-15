import dpath
from luau import indent_block
from luau.convert import from_dict, mark_as_literal, from_dict_to_type
from luau.roblox import write_script
from luau.roblox.wally import require_roblox_wally_package
from luau.path import get_if_module_script, remove_all_path_variants
from src.config import get_data_config, SERVICE_PROXY_PATH, NETWORK_UTIL_WALLY_PATH, MAID_WALLY_PATH, HEADER_WARNING, GET_SUFFIX_KEY, UPDATE_SUFFIX_KEY

def build():
	config = get_data_config()

	build_path = config["build"]["client_path"]
	assert get_if_module_script(build_path), "client datatree must be a ModuleScript, please make sure the client_path only ends with .lua/luau"
	assert not "init" in config["tree"], "\"init\" is reserved for a funciton in the client tree type."
	
	remove_all_path_variants(build_path)
	
	type_tree = {}
	func_tree = {}
	for path, value in dpath.search(config["tree"], '**', yielded=True):
		if type(value) == str:
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
		"",
		"--Packages",
		"local NetworkUtil = " + require_roblox_wally_package(NETWORK_UTIL_WALLY_PATH, is_header=False),
		"local Maid = " + require_roblox_wally_package(MAID_WALLY_PATH, is_header=False),
		"local ServiceProxy = " + require_roblox_wally_package(SERVICE_PROXY_PATH, is_header=False),
		"",
		"--Types",
		"type Maid = Maid.Maid",
		"export type Receiver<T> = () -> T",
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
		"			maid:GiveTask(NetworkUtil.onClientEventAt(updateKey, game.Players.LocalPlayer, function(val)",
		"				values[scope] = val",
		"			end))",
		"			values[scope] = NetworkUtil.invokeServerAt(getKey, game.Players.LocalPlayer)",
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
	write_script(build_path, "\n".join(content))

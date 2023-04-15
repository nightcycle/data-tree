import dpath
from luau import indent_block
from luau.convert import from_dict, mark_as_literal, from_dict_to_type
from luau.roblox import write_script
from luau.roblox.wally import require_roblox_wally_package
from luau.path import get_if_module_script, remove_all_path_variants
from src.config import get_data_config, SIGNAL_WALLY_PATH, NETWORK_UTIL_WALLY_PATH, MAID_WALLY_PATH, HEADER_WARNING, GET_SUFFIX_KEY, UPDATE_SUFFIX_KEY

def build():
	config = get_data_config()

	build_path = config["build"]["server_path"]
	assert get_if_module_script(build_path), "server datatree must be a ModuleScript, please make sure the server_path only ends with .lua/luau"

	remove_all_path_variants(build_path)

	type_tree = {}
	func_tree = {}
	for path, value in dpath.search(config["tree"], '**', yielded=True):
		if type(value) == str:
			dpath.new(func_tree, path, mark_as_literal(f"newDataHandler(\"{path}\", \"{value}\")"))
			dpath.new(type_tree, path, mark_as_literal("DataHandler<string>"))
		elif type(value) == bool:
			dpath.new(func_tree, path, mark_as_literal(f"newNumberHandler(\"{path}\", {value})"))
			dpath.new(type_tree, path, mark_as_literal("DataHandler<boolean>"))
		elif type(value) == int or type(value) == float:
			dpath.new(func_tree, path, mark_as_literal(f"newNumberHandler(\"{path}\", {value})"))
			dpath.new(type_tree, path, mark_as_literal("NumberDataHandler"))

	content = [
		"--!strict",
		HEADER_WARNING,
		"",
		"--Services",
		"local Players = game:GetService(\"Players\")",
		"local DataStoreService = game:GetService(\"DataStoreService\")",
		"local RunService = game:GetService(\"RunService\")",
		"",
		"--Packages",
		"local NetworkUtil = " + require_roblox_wally_package(NETWORK_UTIL_WALLY_PATH, is_header=False),
		"local Maid = " + require_roblox_wally_package(MAID_WALLY_PATH, is_header=False),
		"local Signal = " + require_roblox_wally_package(SIGNAL_WALLY_PATH, is_header=False),
		"",
		"--Types",
		"type Signal = Signal.Signal",
		"type Maid = Maid.Maid",
		"export type UserId = number",
		"export type UserIdKey = string",
		"export type DataHandler<T> = {",
		] + indent_block([
			"__index: DataHandler<T>,",
			"_Maid: Maid,",
			"_IsAlive: boolean,",
			"_Value: T,",
			"-- UpdateEvent: RemoteEvent,",
			"OnChanged: Signal,",
			"ClassName: \"DataHandler\",",
			"Key: UserIdKey,",
			"Player: Player,",
			"DataStore: DataStore,",
			"SetOptions: DataStoreSetOptions,",
			"IncrementOptions: DataStoreIncrementOptions,",
			"init: (maid: Maid) -> nil,",
			"new: (player: Player, scope: string, initialValue: T) -> DataHandler<T>,",
			"Destroy: (self: DataHandler<T>) -> nil,",
			"Get: (self: DataHandler<T>, force: boolean?) -> (T?, boolean),",
			"Set: (self: DataHandler<T>, data: T, force: boolean?) -> boolean,",
			"Update: (self: DataHandler<T>, transformer: (T) -> T, force: boolean?) -> (T?, boolean),",
			"Remove: (self: DataHandler<T>) -> nil,",
		]) + [
		"}",
		"export type SortedDataEntry = {",
		"\tUserId: number,",
		"\tValue: number,",
		"}",
		"export type NumberDataHandler = DataHandler<number> & {",
		] + indent_block([
			"ClassName: \"NumberDataHandler\",",
			"DataStore: OrderedDataStore,",
			"_Value: number,",
			"Increment: (self: NumberDataHandler, delta: number, force: boolean?) -> (number?, boolean),",
			"new: (player: Player, scope: string, initialValue: number) -> NumberDataHandler,",
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
		"--Class",
		"local DataHandler: DataHandler<any> = {} :: any",
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
			"local initialValue = self._Value",
			"local function set()",
			] + indent_block([	
				"local success, errorMessage = pcall(function()",
				"\tself.DataStore:SetAsync(self.Key, data, { self.Player.UserId }, self.SetOptions)",
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
			"self._Value = data",
			"if initialValue ~= data then",
			"\tself.OnChanged:Fire(data)",
			"end",
			"return success",
		]) + [
		"end",
		""
		"function DataHandler:Update(transformer: (any) -> any, force: boolean?)",
		] + indent_block([
			"local initialValue = self._Value",
			"local function update()",
			] + indent_block([	
				"local value = self._Value",
				"local success, msg = pcall(function()",
				"	value = self.DataStore:UpdateAsync(self.Key, transformer)",
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
			]) + [		
			"else",
			"\tvalue = transformer(initialValue)",
			"\tself._Value = value",
			"end",
			"if initialValue ~= value then",
			"\tself.OnChanged:Fire(value)",
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
			"if success and data ~= nil then",
			"\tself._Value = data",
			"end",
			"",
			"return self._Value, success",
		]) + [
		"end",
		"",	
		"function DataHandler.new(player: Player, scope: string, initialValue: any)",
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
			"local self: DataHandler<any> = setmetatable({",
			] + indent_block([		
				"_Maid = maid,",
				"_IsAlive = true,",
				"-- UpdateEvent = updateEvent,",
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
				"local value = self._Value",
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
			]) + [
			"else",
			] + indent_block([	
				"local val: number = self._Value",
				"val += delta",
				"self._Value = value",
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
		"function NumberDataHandler.new(player: Player, scope: string, initialValue: number)",
		] + indent_block([	
			"local self: NumberDataHandler = setmetatable(DataHandler.new(player, scope, initialValue), NumberDataHandler) :: any",
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
			"local function newDataHandler<G>(path: string, val: any): DataHandler<G>",
			] + indent_block([	
				"local handler = DataHandler.new(player, path, val)",
				"playerMaid:GiveTask(handler)",
				"",
				"return handler",
			]) + [
			"end",
			"",
			"local function newNumberHandler(path: string, val: number): NumberDataHandler",
			] + indent_block([	
				"local handler: NumberDataHandler = NumberDataHandler.new(player, path, val) :: any",
				"playerMaid:GiveTask(handler)",
				"",
				"return handler",
			]) + [
			"end",
			"",
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
	write_script(build_path, "\n".join(content))

import dpath
from src.util import get_roblox_type, get_raw_type_name, get_if_optional
from luau import indent_block
from luau.convert import from_dict, mark_as_literal, from_dict_to_type
from luau.roblox import write_script, get_package_require
from luau.path import get_if_module_script, remove_all_path_variants
from src.config import get_data_config, HEADER_WARNING


def build() -> None:
	config = get_data_config()

	build_path = config["build"]["out"]["shared_path"]
	assert get_if_module_script(build_path), "shared datatree must be a ModuleScript, please make sure the client_path only ends with .lua/luau"
	remove_all_path_variants(build_path)
	custom_types = config["types"]

	content: list[str] = [
		"--!strict",
		HEADER_WARNING,
	]

	type_defs: list[str] = []

	def format_type(type_def_input: dict | list, indent_count: int = 0) -> str | dict:
		if type(type_def_input) == dict:
			type_def = {}

			for k, v in type_def_input.items():
				if type(v) == str:
					raw_v = get_raw_type_name(v)
					if raw_v in custom_types:
						if get_if_optional(v):
							type_def[k] = mark_as_literal(raw_v + "?")
						else:
							type_def[k] = mark_as_literal(raw_v)
					else:
						roblox_type = get_roblox_type(raw_v)
						assert roblox_type, f"type {raw_v} at {k} cannot be converted"
						if get_if_optional(v):
							type_def[k] = mark_as_literal(roblox_type + "?")
						else:
							type_def[k] = mark_as_literal(roblox_type)
				else:
					type_def[k] = format_type(v, indent_count+1)

			return type_def
		else:
			str_list = []
			for v in type_def_input:
				str_list.append("\""+v+"\"")

			return " | ".join(str_list)


	for type_name, dict_or_list in custom_types.items():
		formatted_type = format_type(dict_or_list)
		type_str = ""
		if type(formatted_type) == str:
			type_str = formatted_type
		else:
			type_str = from_dict_to_type(formatted_type)

		type_defs.append(f"export type {type_name} = "+ type_str + "\n")

	content += type_defs
	content += [
		"return {}",
	]

	write_script(build_path, "\n".join(content), skip_source_map=True)
	return None

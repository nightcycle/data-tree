# data-tree
## what is this?
This is a command line tool, downloadable with foreman / aftman, that allows you to define a data structure for players and have it generate the scripts supporting the reading / writing of player data as well as replicating it to the client of relevant players.

## why make this?
I want to solve a few problems:
- create a type-safe way to read/write data on the server side
- create a type-safe way to read replicated data on the client side
- store number values in OrderedDataStore format to allow for easy leaderboard creation
- reduce the amount of bandwidth needed to replicate complex data from the server to the client
- encode metadata in accordance to DataStoreV2 standards

You may notice, profile-service does do some of this, especially if you wrap the read / write functions in helper functions that use type-safe custom datatypes. That being said, I consider it more of a backend tool that allows talented developer to build their own system on top, rather than a 1-stop fix.

I feel this is a better solution for any developer willing to embrace automated script writing.

## how does it work?
After downloading with foreman / aftman, follow these steps to set-up your game.
### initialize
In your console run this command:
```sh
datatree init
```
This should create a new file called "datatree.yaml" in the root folder of the repository. Here you can configure the tool.

#### tags
You can create basic dynamic values with pre-determined tags such as:
- DISPLAY_NAME: the user's current display name
- USER_NAME: the user's account name
- USER_ID: the user's id
- GUID: a 32 character unique string usable for identification

You can't use them in any keys (your type structure must be static in this ense), but you can use them in values. You'll see examples in the following sections. In order for a tag to be recognized you need to wrap it in curly brackets, for example: "{USER_NAME}".

#### code strings
You can pass code to the final-script in certain circumstances:
```yaml
is_in_game: "player is {CODE::if game.Players:FindFirstChild(\"{USER_NAME}\")} then \"\" else \"not \"}in game."
```

#### setting the build path
You can set the name / location of the scripts like this:
```yaml
shared_types_roblox_path: game/ReplicatedStorage/Shared/DataTreeTypes
out:
  client_path: out/Client/DataTree.luau # where the client read-only tree is built
  shared_path: out/Shared/DataTreeTypes.luau # where the server tree is built
  server_path: out/Server/DataTreeService.luau # where the server tree is built
```
shared_types_roblox_path is the in-game path for the type script to allow for the requiring of that module.

#### Typing a Tree:
Here's a list of native roblox types that are currently supported:

##### typing Color3s
Can be constructed various ways:

RGB:
```yaml
color::Color3:
  R::int: 125
  G::int: 255
  B::int: 64
```

Hex code:
```yaml
color::Color3: 32a852
```

HSV code:
```yaml
color::Color3:
  H::int: 320 #out of 360
  S::int: 75
  V::int: 30
```

#### typing Booleans
A true / false values:
```yaml
is_first_time::boolean: False
```

##### typing Integers / ints:
A number, except it's rounded to the nearest value
```yaml
deaths::Integer: 10
```
also works:
```yaml
deaths::int: 10
```

#### typing Doubles :
A number, except it's rounded to the nearest hundredth
```yaml
kill_death_rate::Double: 0.75
```
also works:
```yaml
kill_death_rate::double: 0.75
```

#### typing Floats:
A number, with no rounding.
```yaml
kill_death_rate::Float: 0.74999990000001
```
also works:
```yaml
kill_death_rate::float: 0.74999990000001
```

#### typing DateTime
If you want to include DateTime in the datastore you have a few options

From initial join time:
```yaml
join_time::DateTime: NOW
```

From unix timestamp:
```yaml
join_time::DateTime: 1681697303
```

From specificied UTC time:
```yaml
join_time::DateTime:
  Year: 2023
  Month: 4
  Day: 16
  Hour: 22
  Minute: 30
  Second: 16
```
You don't need to include all of the fields, any not included will default to 0. 

#### typing Vector3, Vector3Integer, Vector3Double
Vector3 serializes a vector into floats, allowing for precise storage.
```yaml
position::Vector3:
  X: 534.003463463460
  Y: 238.346034000001
  Z: 58346.3463463466
```

Vector3Integer serializes a vector into integers, allowing for efficient storage.
```yaml
position::Vector3Integer:
  X: 534
  Y: 238
  Z: 58346
```

Vector3Double serializes a vector into doubles, allowing for a balance between efficiency and precision in storage.
```yaml
position::Vector3Double:
  X: 534.00
  Y: 238.34
  Z: 58346.34
```

#### typing Vector2, Vector2Integer, Vector2Double
The same constructors as the Vector3 variants except without the Z Axis

#### typing CFrame, CFrameDouble, CFrameInteger
Allows for the storage of CFrames at varying degrees of precision. Notably the EulerAnglesYXZ are stored as degrees.

The float variant is defined like so:
```yaml
PlayerCFrame::CFrame:
  Position:
    X: 534.003463463460
    Y: 238.346034000001
    Z: 58346.3463463466
  EulerAnglesYXZ:
    X: 30.003463463460
    Y: 18.346034000001
    Z: -96.346346346646
```
The integer variant is defined like so:
```yaml
PlayerCFrame::CFrameInteger:
  Position:
    X: 534
    Y: 238
    Z: 58346
  EulerAnglesYXZ:
    X: 30
    Y: 18
    Z: -96
```
The double variant is defined like so:
```yaml
PlayerCFrame::CFrameDouble:
  Position:
    X: 534.00
    Y: 238.34
    Z: 58346.34
  EulerAnglesYXZ:
    X: 30.00
    Y: 18.34
    Z: -96.34
```

#### typing Roblox Enums:
Here's how you can store a Roblox enum:
```yaml
CarMaterial::Enum.Material: SmoothPlastic
```

#### typing nil Values:
Data doesn't always need to be set, to specify optionally nil data just set:
```yaml
WeaponColor: Color3?
```
or when assigning an initial value in the tree:
```yaml
WeaponColor: nil
```

#### setting custom types
If you wish to store custom-types, define those types here with their default values.

```yaml
types:
  VehicleType: # custom enums can be created as a list of strings
    - "Sedan"
    - "Hatchback"
    - "Truck"
  PermissionData:
    CanDrive: boolean
    CanEdit: boolean
    CanSell: boolean
  PerformanceData:
    Speed: double
    Acceleration: double
    TurnSpeed: double
  VehicleData:
    Name: string
    Type: VehicleType
    Id: string
    PurchaseTime: DateTime
    FrictionCoefficient: double
    Material: Enum.Material
    Appearance:
      Color: Color3
      Skin: string?
    Performance: PerformanceData
```

#### setting tree organization
Allows you to specify how data is organized for players.
```yaml
tree: # the overall structure of the t
  CompanyName: "{DISPLAY_NAME}'s Company" # you don't always need to specify type, in this case it will guess it is a string
  Currency:
    Cash::int: 1000
    VehicleCredits::int: 5
  State::Enum.HumanoidStateType: Dead
  Location::CFrameInteger:
    Position:
      X: 53
      Y: 23
      Z: 5834
    EulerAnglesYXZ:
      X: 0
      Y: 2
      Z: 0
  Garage:
    Slots::List[VehicleData]: [ # this will create a list / array with ordered values
      {
        Name: Lightning McCar,
        Type: Sedan,
        Id: "{GUID}",
        FrictionCoefficient: 0.5,
        Appearance: {
          Color: {
            R: 256,
            G: 128,
            B: 64
          },
          Skin: Lightning,
        },
        Performance: {
          Speed: 12.00,
          Acceleration: 25.00,
          TurnSpeed: 5.00,
        },
      }
    ]
    Permissions::Dict[number, PermissionData?]: {
      12345: {
        CanDrive: false,
        CanEdit: true,
        CanSell: true,
      }
    }
```

#### setting the metadata
You can set the metadata as any dictionary, in this example I'll be using it to set the version:
```yaml
metadata: 
  saved_at::DateTime: NOW
  major: 1
  minor: 2
  patch: 3
  
```

### build
Once you've finished configuring the datatree.yaml file, you can create the actual scripts using this command:
```sh
datatree build
```
With that it should construct the files into the game.

## further improvements
In the future I hope to make various improvements:
- add more types for automatic serialization
- add open-cloud support clt commands for uploading / downloading the datastore
- fix bugs as they're brought to my attention

## conclusion
Thank you for reading! If this helped you out please consider sponsoring my github page @nightcycle.


# TinyLisp → mcfunction（整数移植版）

这是附件 tinylisp-commented.c 的逻辑移植，包含解析器、求值器、全部 21 个原语、环境、闭包、点对列表、quote 和输出。不是完整的 C/double 等价实现。

## 安装与调用

目标：Minecraft Java 1.21.5，pack_format 71。使用函数宏和 1.21.5 新增的 SNBT 字符串转义。较新版本需按目标版本更新 pack.mcmeta；尚未承诺或实测其兼容性。1.21.4 及更早版本不能直接使用这份文件。

把 tinylisp 文件夹放入世界的 datapacks 目录，执行 `/reload`。也可以将 tinylisp-datapack.zip 直接放入 datapacks。

```mcfunction
# 聊天框执行时加 /；mcfunction 文件里不加 /
data modify storage tinylisp:vm source_input set value "(+ 1 2 3)"
function tinylisp:repl
```

输出 `6`。`repl` 是 `run` + `show`，必须有玩家执行者才能用 @s 显示。

```mcfunction
# 命令方块或服务器函数：先计算，再指定接收者
function tinylisp:run
execute as @a run function tinylisp:show
# 查看机器可读结果
data get storage tinylisp:vm result
```

`source_input` 必须是 NBT 字符串。一次可以输入多条表达式，按顺序执行，每条输出占一行。

```mcfunction
data modify storage tinylisp:vm source_input set value "(define square (lambda (x) (* x x))) (square 9)"
function tinylisp:repl
```

输出 `square` 和 `81`。全局定义保留至显式重置；`/reload` 不自动重置已有环境。

```mcfunction
# 清除解释器的所有全局定义和堆，并从头初始化
function tinylisp:reset
```

示例入口：`tinylisp:demo/square`、`tinylisp:demo/closure`、`tinylisp:demo/factorial`。

## Lisp 示例

```lisp
'(a b . c)
(car (cons 1 2))
(if () 10 20)
(or () 7 (/ 1 0))
(let* (a 3) (b (+ a 2)) (* a b))
((lambda (x . rest) (car rest)) 1 2 3)
(define make (lambda (x) (lambda (y) (+ x y))))
(define add7 (make 7))
(add7 3)
(define fact (lambda (n) (if (< n 2) 1 (* n (fact (- n 1))))))
(fact 5)
```

`let*` 保持附件的形式：`(let* (a 3) (b 5) body)`，并非其他 Lisp 常见的嵌套绑定列表语法。lambda 只有一个 body 表达式。

原语：`eval quote cons car cdr + - * / int < eq? pair? or and not cond if let* lambda define`。

## 数据表示和 C 函数映射

| NBT 值 | 含义 |
|---|---|
| `{t:0,n:123}` | 32 位有符号整数 |
| `{t:1,s:"name"}` | 符号，按完整字符串比较，相当于 intern 后的符号身份 |
| `{t:2,i:42}` | cons，指向 `heap[42]` |
| `{t:3,i:42}` | closure，指向与原版相同的 `(vars . body)` / captured environment 结构 |
| `{t:4,p:"add"}` | 原语，内部函数名 |
| `{t:5}` | nil / false |

`heap` 是 cons 节点列表，每个节点为 `{a:<car>,b:<cdr>}`。所有节点字段都是 Lisp 值的 compound，因此无需混合 NBT 基础类型列表。

| C | mcfunction / 处理方式 |
|---|---|
| T / box / ord / num | 字段 `t` / compound 构造 / 字段 `i` / 字段 `n` |
| atom / equ | 符号直接存字符串；`equal` 用 data modify 的 success 比较值 |
| cons / car / cdr / pair | 同名函数，宏下标访问 heap |
| closure / f_lambda | `prim/lambda` |
| assoc / evlis / bind / apply / eval | 同名函数，参数经 `call` 传递，栈帧保存在 `frames` |
| reduce | `reduce_body`，使用 apply 的当前栈帧 |
| f_* | `prim/*` |
| look / get / seeing / scan | `peek` / #pos / 字符判断 / `scan` |
| Read / list / quote / atomic / parse | `read` / `list` / `read_quote` / read 的数字与符号分支 |
| print / printlist | 同名函数，将片段追加至 `output`；`show` 用 NBT 文本显示 |
| gc | 下一次 run 开始时裁去最新全局环境之后的临时节点 |
| main | `load` / `reset` / `run_loop` / `repl` |

`result` 是最后一条表达式的值，`output` 是包含所有表达式打印结果的字符串片段列表。
返回的 cons/closure 索引可以在本次运行之后读取，但不能当成永久外部句柄：下一次 run 的 gc 可能移除没有被全局环境持有的临时节点。需要保留值时用 `(define name expression)`。

## 已知差异与限制

- **数值不是 double**：只解析十进制整数，可带 + 或 -。小数、科学计数法等文本会被当成符号；不会执行浮点运算。0 仍然是真值，只有 nil 为假。
- 记分板数值范围为 -2147483648…2147483647，整数加减乘和字面量累积溢出会按 32 位回绕。`/` 每一步向零截断，`(/ 7 2)` 为 3；`int` 对整数保持不变。
- `eq?` 对整数按整数值比较；无法复现 C double 的位级比较（如 +0/-0、NaN）。cons 和 closure 仍按类型和堆索引比较。
- 原附件 `pair?` 的实际实现只接受 CONS，尽管注释说包含 closure。本移植遵循实现：对 closure 返回 nil。
- 原语打印名使用内部名称，例如 `<add>` 而不是 `<+>`；closure 显示 `{heap_index}`，不是 C 原来的栈地址。
- 无 stdin 或永久交互循环：源程序通过 storage 提供，输出通过 storage / tellraw 提供。
- 没有实现 double 运行库、C 共享堆内存布局、1024 单元内存上限和 40 字节 token 缓冲。堆采用 NBT 动态列表；垃圾清理保持原版“保留最新全局环境之前的分配”思想，旧的全局环境链不会被压缩。
- 源码长度上限 512 字符、递归函数栈帧上限 64、每次 run 最多 4000 次内部封装函数调用。达到限制返回 ERR。长 token 的扫描和 gc 也会消耗游戏命令预算。
- Minecraft 自身的函数命令预算仍然有效：复杂程序可能先触及 maxCommandChainLength，导致游戏提前中断，不能保证解释器自行输出 ERR。发生中断时执行 `tinylisp:reset` 恢复状态。此实现适合短程序验证；NBT 查找、复制、宏调用和递归开销很大，不是高性能 Lisp VM。
- 非数值算术、除零、语法错误或解释器限制设置 `#error tl=1`，最终 result 为 ERR。其他未绑定符号/错误类型按原版返回 ERR 符号；ERR 本身仍是真值。错误之前已完成的 define 不回滚。
- 增加了括号与点对尾部检查；空 cond 返回 ERR，避免原版潜在死循环。单引号也作为 token 分隔符，这是对原 scan 的轻微修正。不是 Common Lisp / Scheme 的完整语法：没有字符串字面量、注释、begin、set! 等扩展。
- 单个解释器共享一个 storage。run 同步执行并使用 busy 标志；不是多玩家独立会话。

## 验证与文件

共 110 个 mcfunction 文件。外层封装函数负责压栈/弹栈和预算，`body/` 内执行函数主体；原语使用 apply 的当前帧，嵌套调用压入新帧。

本地 `verify.py` 执行这份生成代码所用的命令子集，覆盖 43 个行为用例及静态函数引用检查，包括递归、闭包、短路、dot/rest 参数、跨调用保留、负数除法和错误输入。

**未启动 Minecraft 服务器验证。模拟器不验证 Brigadier 的真实解析、NBT 数字 tag 类型、游戏命令预算和所有运行时细节，因此不能视为游戏内验收。**

分发文件：

- `tinylisp-datapack.zip`：直接安装的数据包（根目录为 pack.mcmeta 与 data）。
- `tinylisp-source.zip`：数据包、此说明、build.py 生成器、verify.py 本地命令模拟器以及原始 C 附件。

源码包内执行：

```sh
python3 build.py
python3 verify.py
```

build.py 重新生成 mcfunction，不在 Minecraft 运行时使用；玩家无需安装 Python。

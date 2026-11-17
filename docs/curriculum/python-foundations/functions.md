# Python 函数基础

项目原创教学讲义，适用于 Python 3 的基础学习；不是北理工官方教材。参考链接仅用于核对语义，不代表复制官方正文。预计学习30分钟：阅读12分钟、手动跟踪示例10分钟、测验8分钟。

## 1. 函数定义与调用
函数把一个可重复执行的任务封装起来。`def` 执行时创建函数对象，并将名字绑定到它；缩进的函数体通常在调用时执行。定义和调用是两个动作。
```python
def double(x):
    return x * 2

answer = double(3)  # answer 为 6
```
`double` 是函数名，定义处的 `x` 是形参，调用处的 `3` 是实参。括号中的表达式会先求值，再将得到的对象传给函数。先写清楚函数的输入、处理步骤和输出，可以降低理解难度。

## 2. 参数与调用方式
普通参数可以按位置或名称传入：
```python
def subtract(a, b):
    return a - b

subtract(8, 3)        # 5
subtract(b=3, a=8)    # 5
```
位置实参按顺序匹配，关键字实参按参数名匹配。给同一参数重复赋值，或遗漏没有默认值的必需参数，通常会引发 TypeError。基础调用中，普通位置实参应写在关键字实参之前。

## 3. 返回值与 print
`return` 结束当前一次函数调用，并把值交给调用者；它之后同一路径上的语句不再执行。`print` 向输出流显示内容，不等于把该内容作为返回值。不执行带值的 return（包括执行裸 return）时，函数返回 None。
```python
def shown(x):
    print(x)

value = shown(5)  # 显示 5，但 value 是 None
```
`return a, b` 将两个值打包成一个元组返回，调用者可用 `x, y = ...` 解包。函数可以调用其他函数，把返回值继续用于表达式。

## 4. 局部作用域与对象
每次函数调用都有自己的局部名称。函数内对局部名字重新绑定，通常不会更改同名全局名字。传参是绑定对象：对列表等可变对象原地修改，调用者可以观察到；只把局部参数名重新绑定到新对象，不会重绑调用者的变量。
```python
def append_one(items):
    items.append(1)

values = []
append_one(values)  # values 变为 [1]
```
不要把“参数名是局部的”误解为“对象一定被复制”。本课不依靠 global 修改外部状态，优先让函数显式接收参数并返回结果。

## 5. 默认参数
默认值在执行函数定义时求值，而不是每次调用都重新求值。可变默认对象可能被多次调用共享：
```python
def collect(x, items=None):
    if items is None:
        items = []
    items.append(x)
    return items
```
这里每次省略 items 时创建新列表；如果主动传入同一个列表，仍会修改该列表。基础练习应区分默认值、实参和局部变量。

## 6. 自检与常见错误
用自己的话解释形参与实参；预测一个带 return 的调用结果；区分打印值与返回值；跟踪关键字参数匹配；说明局部名字与可变对象的差别。编写 add(a, b) 后分别检查 add(2, 3)、add(b=3, a=2)。不要只背关键字，先画出输入到返回值的过程。

参考：https://docs.python.org/zh-cn/3.12/tutorial/controlflow.html#defining-functions
参考：https://docs.python.org/zh-cn/3.12/tutorial/classes.html#python-scopes-and-namespaces

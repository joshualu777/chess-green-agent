import re

def parse_tags(str_with_tags):
    pairs = re.findall(r"<(.*?)>(.*?)</\1>", str_with_tags, re.DOTALL)
    result = {}
    for tag, content in pairs:
        value = content.strip()
        if not tag in result:
            result[tag] = []
        result[tag].append(value)
    return result


if __name__ == "__main__":
    test_str = "<tag1>Hello</tag1> some text <tag2>World</tag2> <tag2>Again</tag2>"
    print(parse_tags(test_str))

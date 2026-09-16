"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// cloudfunctions/draw/index.ts
var index_exports = {};
__export(index_exports, {
  main: () => main
});
module.exports = __toCommonJS(index_exports);

// cloudfunctions/draw/core.ts
var import_node_crypto = require("node:crypto");

// cloudfunctions/draw/cards.generated.json
var cards_generated_default = [
  {
    id: "card-001",
    title: "\u5148\u770B\u8BA1\u5212",
    shortAnswer: "\u5F00\u76D8\u524D\u7684\u6E05\u9192\uFF0C\u6BD4\u76D8\u4E2D\u7684\u53CD\u5E94\u66F4\u53EF\u9760\u3002",
    reflectionQuestion: "\u4ECA\u5929\u7684\u884C\u52A8\u6761\u4EF6\u5199\u6E05\u695A\u4E86\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-002",
    title: "\u7ED9\u60C5\u7EEA\u964D\u6E29",
    shortAnswer: "\u6025\u8FEB\u611F\u4E0D\u7B49\u4E8E\u91CD\u8981\u6027\u3002",
    reflectionQuestion: "\u6B64\u523B\u662F\u4EC0\u4E48\u5728\u50AC\u4FC3\u4F60\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-003",
    title: "\u68C0\u67E5\u524D\u63D0",
    shortAnswer: "\u7ED3\u8BBA\u7AD9\u5F97\u4F4F\uFF0C\u524D\u63D0\u4E5F\u8981\u7AD9\u5F97\u4F4F\u3002",
    reflectionQuestion: "\u54EA\u9879\u524D\u63D0\u6700\u53EF\u80FD\u5931\u6548\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-004",
    title: "\u7559\u51FA\u7A7A\u767D",
    shortAnswer: "\u6CA1\u6709\u52A8\u4F5C\uFF0C\u4E5F\u662F\u4E00\u79CD\u5B8C\u6574\u9009\u62E9\u3002",
    reflectionQuestion: "\u4ECA\u5929\u662F\u5426\u771F\u7684\u5FC5\u987B\u884C\u52A8\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-005",
    title: "\u533A\u5206\u6D88\u606F",
    shortAnswer: "\u65B0\u6D88\u606F\u4E0D\u4E00\u5B9A\u5E26\u6765\u65B0\u4E8B\u5B9E\u3002",
    reflectionQuestion: "\u4F60\u770B\u5230\u7684\u662F\u4E8B\u5B9E\u8FD8\u662F\u8F6C\u8FF0\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-006",
    title: "\u786E\u8BA4\u8FB9\u754C",
    shortAnswer: "\u5148\u77E5\u9053\u627F\u53D7\u8303\u56F4\uFF0C\u518D\u8C08\u5224\u65AD\u3002",
    reflectionQuestion: "\u6700\u574F\u60C5\u5F62\u662F\u5426\u5728\u627F\u53D7\u8303\u56F4\u5185\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-007",
    title: "\u6162\u534A\u62CD",
    shortAnswer: "\u591A\u4E00\u6B21\u6838\u5BF9\uFF0C\u5C11\u4E00\u6B21\u51B2\u52A8\u3002",
    reflectionQuestion: "\u8FD8\u6709\u54EA\u9879\u4FE1\u606F\u5C1A\u672A\u6838\u5BF9\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-008",
    title: "\u56DE\u5230\u76EE\u6807",
    shortAnswer: "\u77ED\u671F\u6CE2\u52A8\u4E0D\u5E94\u6539\u5199\u957F\u671F\u7528\u9014\u3002",
    reflectionQuestion: "\u8FD9\u7B14\u8D44\u91D1\u539F\u672C\u8981\u89E3\u51B3\u4EC0\u4E48\u95EE\u9898\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-009",
    title: "\u89C2\u5BDF\u8EAB\u4F53",
    shortAnswer: "\u7D27\u7EF7\u5E38\u5E38\u65E9\u4E8E\u9519\u8BEF\u51B3\u5B9A\u51FA\u73B0\u3002",
    reflectionQuestion: "\u4F60\u7684\u8EAB\u4F53\u6B63\u5728\u53D1\u51FA\u4EC0\u4E48\u4FE1\u53F7\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-010",
    title: "\u9884\u7559\u53CD\u8BC1",
    shortAnswer: "\u597D\u5224\u65AD\u4E5F\u9700\u8981\u88AB\u53CD\u9A73\u7684\u5165\u53E3\u3002",
    reflectionQuestion: "\u4EC0\u4E48\u8BC1\u636E\u4F1A\u8BA9\u4F60\u6539\u53D8\u770B\u6CD5\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-011",
    title: "\u63A5\u53D7\u9519\u8FC7",
    shortAnswer: "\u9519\u8FC7\u4E0D\u7B49\u4E8E\u635F\u5931\u3002",
    reflectionQuestion: "\u4F60\u5BB3\u6015\u9519\u8FC7\u7684\u662F\u673A\u4F1A\u8FD8\u662F\u8BA4\u540C\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-012",
    title: "\u6E05\u70B9\u6CE8\u610F\u529B",
    shortAnswer: "\u6CE8\u610F\u529B\u4E5F\u662F\u6709\u9650\u8D44\u6E90\u3002",
    reflectionQuestion: "\u4ECA\u5929\u6700\u503C\u5F97\u8DDF\u8E2A\u7684\u4E00\u4EF6\u4E8B\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u5F00\u76D8\u524D\u68C0\u67E5\u72B6\u6001\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u6295\u8D44\u5EFA\u8BAE\u3002",
    category: "preopen",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-013",
    title: "\u6536\u76D8\u518D\u770B",
    shortAnswer: "\u4EF7\u683C\u505C\u4E0B\u540E\uFF0C\u7406\u7531\u624D\u5BB9\u6613\u88AB\u770B\u6E05\u3002",
    reflectionQuestion: "\u4ECA\u5929\u7684\u5224\u65AD\u4F9D\u636E\u53D1\u751F\u53D8\u5316\u4E86\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-014",
    title: "\u4E8B\u5B9E\u4E0E\u611F\u53D7",
    shortAnswer: "\u8D26\u6237\u611F\u53D7\u4E0D\u80FD\u66FF\u4EE3\u4E8B\u5B9E\u8BB0\u5F55\u3002",
    reflectionQuestion: "\u4F60\u80FD\u5206\u522B\u5199\u4E0B\u4E8B\u5B9E\u4E0E\u611F\u53D7\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-015",
    title: "\u590D\u6838\u504F\u5DEE",
    shortAnswer: "\u7ED3\u679C\u6B63\u786E\uFF0C\u4E0D\u4EE3\u8868\u8FC7\u7A0B\u6B63\u786E\u3002",
    reflectionQuestion: "\u4ECA\u5929\u7684\u8FC7\u7A0B\u6709\u54EA\u4E9B\u5076\u7136\u6027\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-016",
    title: "\u8BB0\u5F55\u610F\u5916",
    shortAnswer: "\u610F\u5916\u4E4B\u5904\u5F80\u5F80\u6700\u503C\u5F97\u590D\u76D8\u3002",
    reflectionQuestion: "\u54EA\u4E00\u5E55\u6700\u8D85\u51FA\u4F60\u7684\u9884\u671F\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-017",
    title: "\u68C0\u67E5\u4E00\u81F4",
    shortAnswer: "\u884C\u52A8\u4E0E\u8BA1\u5212\u7684\u8DDD\u79BB\u9700\u8981\u88AB\u770B\u89C1\u3002",
    reflectionQuestion: "\u4ECA\u5929\u54EA\u91CC\u504F\u79BB\u4E86\u539F\u8BA1\u5212\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-018",
    title: "\u505C\u6B62\u5F52\u548E",
    shortAnswer: "\u5E02\u573A\u6CA1\u6709\u4E49\u52A1\u914D\u5408\u4E2A\u4EBA\u53D9\u4E8B\u3002",
    reflectionQuestion: "\u4F60\u662F\u5426\u628A\u7ED3\u679C\u5F52\u548E\u4E8E\u5355\u4E00\u539F\u56E0\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-019",
    title: "\u7ED9\u7ED3\u8BBA\u7559\u767D",
    shortAnswer: "\u4E00\u5929\u7684\u6570\u636E\u5F88\u5C11\u8DB3\u4EE5\u8BC1\u660E\u957F\u671F\u5224\u65AD\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u7ED3\u8BBA\u4E0B\u5F97\u8FC7\u65E9\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-020",
    title: "\u590D\u76D8\u4FE1\u606F\u6E90",
    shortAnswer: "\u53EF\u9760\u6765\u6E90\u7ECF\u5F97\u8D77\u56DE\u770B\u3002",
    reflectionQuestion: "\u4ECA\u5929\u54EA\u6761\u4FE1\u606F\u503C\u5F97\u7EE7\u7EED\u4FDD\u7559\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-021",
    title: "\u8FA8\u8BA4\u8FD0\u6C14",
    shortAnswer: "\u987A\u5229\u4E5F\u53EF\u80FD\u53EA\u662F\u968F\u673A\u6CE2\u52A8\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u7ED3\u679C\u4E0D\u80FD\u5F52\u529F\u4E8E\u80FD\u529B\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-022",
    title: "\u6536\u597D\u60C5\u7EEA",
    shortAnswer: "\u6536\u76D8\u540E\u4E0D\u5FC5\u7EE7\u7EED\u548C\u6CE2\u52A8\u4E89\u8BBA\u3002",
    reflectionQuestion: "\u4EC0\u4E48\u80FD\u5E2E\u52A9\u4F60\u9000\u51FA\u4EA4\u6613\u72B6\u6001\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-023",
    title: "\u770B\u89C1\u6210\u672C",
    shortAnswer: "\u9891\u7E41\u51B3\u7B56\u4F1A\u6D88\u8017\u5224\u65AD\u8D28\u91CF\u3002",
    reflectionQuestion: "\u4ECA\u5929\u6709\u591A\u5C11\u52A8\u4F5C\u5E76\u975E\u5FC5\u8981\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-024",
    title: "\u5199\u4E0B\u4E00\u53E5",
    shortAnswer: "\u7B80\u77ED\u8BB0\u5F55\u6BD4\u4E8B\u540E\u91CD\u6784\u66F4\u8BDA\u5B9E\u3002",
    reflectionQuestion: "\u7528\u4E00\u53E5\u8BDD\u6982\u62EC\u4ECA\u5929\u5B66\u5230\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u6536\u76D8\u540E\u590D\u76D8\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u8BC1\u5238\u6216\u5F53\u65E5\u884C\u60C5\u3002",
    category: "close",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-025",
    title: "\u56DE\u5230\u5168\u5C40",
    shortAnswer: "\u5355\u65E5\u566A\u58F0\u9000\u53BB\uFF0C\u7ED3\u6784\u624D\u4F1A\u51FA\u73B0\u3002",
    reflectionQuestion: "\u7EC4\u5408\u662F\u5426\u4ECD\u670D\u52A1\u4E8E\u539F\u76EE\u6807\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-026",
    title: "\u68C0\u67E5\u96C6\u4E2D",
    shortAnswer: "\u719F\u6089\u611F\u53EF\u80FD\u63A9\u76D6\u96C6\u4E2D\u98CE\u9669\u3002",
    reflectionQuestion: "\u98CE\u9669\u662F\u5426\u8FC7\u5EA6\u96C6\u4E2D\u5728\u540C\u4E00\u903B\u8F91\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-027",
    title: "\u6838\u5BF9\u671F\u9650",
    shortAnswer: "\u65F6\u95F4\u76EE\u6807\u51B3\u5B9A\u53EF\u627F\u53D7\u7684\u6CE2\u52A8\u3002",
    reflectionQuestion: "\u8D44\u91D1\u671F\u9650\u662F\u5426\u4E0E\u5B89\u6392\u5339\u914D\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-028",
    title: "\u6574\u7406\u5047\u8BBE",
    shortAnswer: "\u6CA1\u6709\u5199\u4E0B\u7684\u5047\u8BBE\u6700\u5BB9\u6613\u6F02\u79FB\u3002",
    reflectionQuestion: "\u6838\u5FC3\u5047\u8BBE\u8FD8\u80FD\u88AB\u6E05\u695A\u8868\u8FBE\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-029",
    title: "\u5220\u9664\u566A\u58F0",
    shortAnswer: "\u4FE1\u606F\u8D8A\u591A\uFF0C\u4E0D\u4E00\u5B9A\u5224\u65AD\u8D8A\u597D\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u5173\u6CE8\u9879\u53EF\u4EE5\u505C\u6B62\u8DDF\u8E2A\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-030",
    title: "\u5BA1\u89C6\u76F8\u5173",
    shortAnswer: "\u540D\u5B57\u4E0D\u540C\uFF0C\u4E0D\u4EE3\u8868\u98CE\u9669\u6765\u6E90\u4E0D\u540C\u3002",
    reflectionQuestion: "\u5404\u90E8\u5206\u662F\u5426\u5171\u4EAB\u540C\u4E00\u79CD\u98CE\u9669\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-031",
    title: "\u9884\u60F3\u538B\u529B",
    shortAnswer: "\u5E73\u9759\u65F6\u66F4\u9002\u5408\u8BBE\u8BA1\u5E94\u5BF9\u3002",
    reflectionQuestion: "\u538B\u529B\u60C5\u5F62\u4E0B\u4F60\u4F1A\u5982\u4F55\u4FDD\u6301\u7EAA\u5F8B\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-032",
    title: "\u8BC4\u4F30\u7CBE\u529B",
    shortAnswer: "\u590D\u6742\u5B89\u6392\u9700\u8981\u6301\u7EED\u7EF4\u62A4\u6210\u672C\u3002",
    reflectionQuestion: "\u4F60\u6709\u7CBE\u529B\u7406\u89E3\u5E76\u7EF4\u62A4\u5B83\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-033",
    title: "\u786E\u8BA4\u7528\u9014",
    shortAnswer: "\u7528\u9014\u53D8\u5316\uFF0C\u98CE\u9669\u8FB9\u754C\u4E5F\u4F1A\u53D8\u5316\u3002",
    reflectionQuestion: "\u8FD1\u671F\u662F\u5426\u51FA\u73B0\u65B0\u7684\u8D44\u91D1\u9700\u6C42\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-034",
    title: "\u770B\u957F\u671F\u8BB0\u5F55",
    shortAnswer: "\u591A\u671F\u8BB0\u5F55\u6BD4\u5355\u6B21\u611F\u53D7\u66F4\u53EF\u4FE1\u3002",
    reflectionQuestion: "\u957F\u671F\u884C\u4E3A\u91CC\u6709\u4EC0\u4E48\u91CD\u590D\u6A21\u5F0F\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-035",
    title: "\u8865\u5145\u53CD\u65B9",
    shortAnswer: "\u4E3B\u52A8\u5BFB\u627E\u53CD\u65B9\u80FD\u964D\u4F4E\u786E\u8BA4\u504F\u8BEF\u3002",
    reflectionQuestion: "\u6700\u6709\u529B\u7684\u53CD\u65B9\u8BC1\u636E\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-036",
    title: "\u4F11\u606F\u4E5F\u662F\u529F\u8BFE",
    shortAnswer: "\u79BB\u5F00\u5C4F\u5E55\u6709\u52A9\u4E8E\u6062\u590D\u5224\u65AD\u529B\u3002",
    reflectionQuestion: "\u8FD9\u4E2A\u5468\u672B\u80FD\u5426\u771F\u6B63\u6682\u505C\u5173\u6CE8\uFF1F",
    boundary: "\u7528\u4E8E\u5468\u672B\u7EC4\u5408\u4F53\u68C0\uFF0C\u4EC5\u63D0\u4F9B\u6559\u80B2\u6027\u53CD\u601D\u3002",
    category: "weekend",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-037",
    title: "\u8BC1\u636E\u7B49\u7EA7",
    shortAnswer: "\u89C2\u70B9\u7684\u97F3\u91CF\uFF0C\u4E0D\u4EE3\u8868\u8BC1\u636E\u7684\u5F3A\u5EA6\u3002",
    reflectionQuestion: "\u6700\u5173\u952E\u8BC1\u636E\u6765\u81EA\u54EA\u91CC\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-038",
    title: "\u4E00\u624B\u6765\u6E90",
    shortAnswer: "\u8D8A\u63A5\u8FD1\u539F\u59CB\u6750\u6599\uFF0C\u8BEF\u5DEE\u901A\u5E38\u8D8A\u5C11\u3002",
    reflectionQuestion: "\u4F60\u770B\u8FC7\u539F\u59CB\u62AB\u9732\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-039",
    title: "\u6837\u672C\u4E4B\u5916",
    shortAnswer: "\u5C11\u6570\u6848\u4F8B\u4E0D\u80FD\u4EE3\u8868\u666E\u904D\u89C4\u5F8B\u3002",
    reflectionQuestion: "\u6837\u672C\u662F\u5426\u8DB3\u591F\u4E14\u6709\u4EE3\u8868\u6027\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-040",
    title: "\u76F8\u5173\u4E0E\u56E0\u679C",
    shortAnswer: "\u540C\u65F6\u53D1\u751F\uFF0C\u4E0D\u7B49\u4E8E\u5F7C\u6B64\u5BFC\u81F4\u3002",
    reflectionQuestion: "\u662F\u5426\u5B58\u5728\u7B2C\u4E09\u4E2A\u89E3\u91CA\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-041",
    title: "\u65F6\u95F4\u987A\u5E8F",
    shortAnswer: "\u56E0\u679C\u5224\u65AD\u9700\u8981\u5148\u540E\u5173\u7CFB\u3002",
    reflectionQuestion: "\u8BC1\u636E\u7684\u65F6\u95F4\u987A\u5E8F\u6210\u7ACB\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-042",
    title: "\u5E78\u5B58\u504F\u5DEE",
    shortAnswer: "\u88AB\u770B\u89C1\u7684\u6210\u529F\u5E38\u5E38\u53EA\u662F\u90E8\u5206\u6837\u672C\u3002",
    reflectionQuestion: "\u6D88\u5931\u7684\u5931\u8D25\u6848\u4F8B\u5728\u54EA\u91CC\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-043",
    title: "\u57FA\u51C6\u610F\u8BC6",
    shortAnswer: "\u6CA1\u6709\u57FA\u51C6\uFF0C\u53D8\u5316\u96BE\u4EE5\u89E3\u91CA\u3002",
    reflectionQuestion: "\u4F60\u7528\u4EC0\u4E48\u4F5C\u4E3A\u6BD4\u8F83\u57FA\u51C6\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-044",
    title: "\u53CD\u4E8B\u5B9E",
    shortAnswer: "\u597D\u7684\u89E3\u91CA\u4E5F\u8981\u56DE\u7B54\u53E6\u4E00\u79CD\u53EF\u80FD\u3002",
    reflectionQuestion: "\u5982\u679C\u539F\u56E0\u4E0D\u5B58\u5728\uFF0C\u7ED3\u679C\u4F1A\u600E\u6837\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-045",
    title: "\u6570\u636E\u53E3\u5F84",
    shortAnswer: "\u540C\u540D\u6307\u6807\u53EF\u80FD\u6709\u4E0D\u540C\u5B9A\u4E49\u3002",
    reflectionQuestion: "\u53E3\u5F84\u3001\u533A\u95F4\u548C\u6765\u6E90\u4E00\u81F4\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-046",
    title: "\u66F4\u65B0\u9891\u7387",
    shortAnswer: "\u65E7\u8BC1\u636E\u53EF\u80FD\u65E0\u6CD5\u89E3\u91CA\u65B0\u73AF\u5883\u3002",
    reflectionQuestion: "\u5173\u952E\u6570\u636E\u6700\u8FD1\u4F55\u65F6\u66F4\u65B0\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-047",
    title: "\u5229\u76CA\u5173\u7CFB",
    shortAnswer: "\u8868\u8FBE\u8005\u7684\u7ACB\u573A\u4F1A\u5F71\u54CD\u53D9\u4E8B\u3002",
    reflectionQuestion: "\u4FE1\u606F\u63D0\u4F9B\u8005\u53EF\u80FD\u6709\u54EA\u4E9B\u5229\u76CA\u5173\u7CFB\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-048",
    title: "\u53EF\u590D\u6838\u6027",
    shortAnswer: "\u4E0D\u80FD\u590D\u6838\u7684\u65AD\u8A00\u53EA\u80FD\u6682\u5B58\u3002",
    reflectionQuestion: "\u522B\u4EBA\u80FD\u6CBF\u540C\u4E00\u8DEF\u5F84\u590D\u6838\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u8BC1\u636E\u8D28\u91CF\u68C0\u67E5\uFF0C\u4E0D\u66FF\u4EE3\u72EC\u7ACB\u7814\u7A76\u4E0E\u4E13\u4E1A\u610F\u89C1\u3002",
    category: "evidence",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-049",
    title: "\u5148\u770B\u4E0B\u884C",
    shortAnswer: "\u6F5C\u5728\u56DE\u62A5\u4E4B\u5916\uFF0C\u4E0B\u884C\u540C\u6837\u771F\u5B9E\u3002",
    reflectionQuestion: "\u4E0D\u5229\u60C5\u5F62\u4F1A\u5F71\u54CD\u54EA\u4E9B\u751F\u6D3B\u76EE\u6807\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-050",
    title: "\u627F\u53D7\u4E0E\u5BB9\u5FCD",
    shortAnswer: "\u53E3\u5934\u5BB9\u5FCD\u548C\u771F\u5B9E\u627F\u53D7\u53EF\u80FD\u4E0D\u540C\u3002",
    reflectionQuestion: "\u8FC7\u53BB\u6CE2\u52A8\u4E2D\u4F60\u7684\u771F\u5B9E\u53CD\u5E94\u5982\u4F55\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-051",
    title: "\u6D41\u52A8\u6027",
    shortAnswer: "\u9700\u8981\u7528\u94B1\u65F6\uFF0C\u6D41\u52A8\u6027\u6BD4\u60F3\u8C61\u66F4\u91CD\u8981\u3002",
    reflectionQuestion: "\u8D44\u91D1\u662F\u5426\u53EF\u80FD\u63D0\u524D\u4F7F\u7528\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-052",
    title: "\u5C3E\u90E8\u60C5\u5F62",
    shortAnswer: "\u4F4E\u6982\u7387\u4E8B\u4EF6\u4E5F\u53EF\u80FD\u5E26\u6765\u5927\u5F71\u54CD\u3002",
    reflectionQuestion: "\u6781\u7AEF\u60C5\u5F62\u4E0B\u6709\u54EA\u4E9B\u8106\u5F31\u70B9\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-053",
    title: "\u76F8\u5173\u98CE\u9669",
    shortAnswer: "\u5171\u540C\u4E0B\u8DCC\u65F6\uFF0C\u8868\u9762\u5206\u6563\u53EF\u80FD\u5931\u6548\u3002",
    reflectionQuestion: "\u98CE\u9669\u6765\u6E90\u771F\u7684\u76F8\u4E92\u72EC\u7ACB\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-054",
    title: "\u8BA4\u77E5\u8FB9\u754C",
    shortAnswer: "\u4E0D\u7406\u89E3\u672C\u8EAB\u5C31\u662F\u4E00\u79CD\u98CE\u9669\u3002",
    reflectionQuestion: "\u54EA\u4E00\u90E8\u5206\u4F60\u4ECD\u65E0\u6CD5\u89E3\u91CA\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-055",
    title: "\u89C4\u5219\u5F39\u6027",
    shortAnswer: "\u89C4\u5219\u592A\u590D\u6742\uFF0C\u538B\u529B\u4E0B\u66F4\u96BE\u6267\u884C\u3002",
    reflectionQuestion: "\u98CE\u9669\u89C4\u5219\u662F\u5426\u7B80\u5355\u5230\u80FD\u88AB\u6267\u884C\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-056",
    title: "\u671F\u9650\u9519\u914D",
    shortAnswer: "\u957F\u671F\u8D44\u4EA7\u4E0E\u77ED\u671F\u7528\u6B3E\u53EF\u80FD\u51B2\u7A81\u3002",
    reflectionQuestion: "\u65F6\u95F4\u5B89\u6392\u662F\u5426\u5B58\u5728\u9519\u914D\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-057",
    title: "\u6760\u6746\u610F\u8BC6",
    shortAnswer: "\u653E\u5927\u7ED3\u679C\uFF0C\u4E5F\u4F1A\u538B\u7F29\u7B49\u5F85\u7A7A\u95F4\u3002",
    reflectionQuestion: "\u4F60\u662F\u5426\u7406\u89E3\u5168\u90E8\u7EA6\u675F\u4E0E\u6210\u672C\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-058",
    title: "\u610F\u5916\u5173\u8054",
    shortAnswer: "\u98CE\u9669\u5E38\u4ECE\u672A\u8BB0\u5F55\u7684\u5173\u8054\u5904\u4F20\u5BFC\u3002",
    reflectionQuestion: "\u8FD8\u6709\u54EA\u4E9B\u5171\u540C\u66B4\u9732\u88AB\u5FFD\u7565\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-059",
    title: "\u51B3\u7B56\u4F59\u5730",
    shortAnswer: "\u4FDD\u7559\u4F59\u5730\uFF0C\u624D\u80FD\u5E94\u5BF9\u672A\u77E5\u53D8\u5316\u3002",
    reflectionQuestion: "\u4E0D\u5229\u53D8\u5316\u540E\u8FD8\u6709\u8C03\u6574\u7A7A\u95F4\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-060",
    title: "\u98CE\u9669\u8BED\u8A00",
    shortAnswer: "\u6A21\u7CCA\u7684\u62C5\u5FC3\u9700\u8981\u53D8\u6210\u6E05\u695A\u63CF\u8FF0\u3002",
    reflectionQuestion: "\u80FD\u5426\u5177\u4F53\u5199\u51FA\u6700\u62C5\u5FC3\u7684\u60C5\u5F62\uFF1F",
    boundary: "\u7528\u4E8E\u98CE\u9669\u6559\u80B2\uFF0C\u4E0D\u7ED9\u51FA\u4ED3\u4F4D\u3001\u4E70\u5356\u6216\u6B62\u635F\u6307\u4EE4\u3002",
    category: "risk",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-061",
    title: "\u547D\u540D\u60C5\u7EEA",
    shortAnswer: "\u88AB\u8BF4\u6E05\u7684\u60C5\u7EEA\uFF0C\u66F4\u4E0D\u5BB9\u6613\u63A5\u7BA1\u51B3\u5B9A\u3002",
    reflectionQuestion: "\u6B64\u523B\u6700\u5F3A\u70C8\u7684\u60C5\u7EEA\u53EB\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-062",
    title: "\u6025\u4E8E\u8BC1\u660E",
    shortAnswer: "\u8BC1\u660E\u81EA\u5DF1\u53EF\u80FD\u906E\u4F4F\u771F\u6B63\u76EE\u6807\u3002",
    reflectionQuestion: "\u4F60\u662F\u5728\u89E3\u51B3\u95EE\u9898\u8FD8\u662F\u8BC1\u660E\u5224\u65AD\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-063",
    title: "\u6BD4\u8F83\u538B\u529B",
    shortAnswer: "\u522B\u4EBA\u7684\u7ED3\u679C\u4E0D\u5C5E\u4E8E\u4F60\u7684\u51B3\u7B56\u6761\u4EF6\u3002",
    reflectionQuestion: "\u6BD4\u8F83\u6B63\u5728\u6539\u53D8\u4F60\u7684\u8282\u594F\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-064",
    title: "\u635F\u5931\u611F\u53D7",
    shortAnswer: "\u635F\u5931\u5E26\u6765\u7684\u75DB\u611F\u4F1A\u653E\u5927\u77ED\u671F\u51B2\u52A8\u3002",
    reflectionQuestion: "\u4F60\u662F\u5426\u53EA\u60F3\u7ACB\u523B\u6D88\u9664\u75DB\u611F\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-065",
    title: "\u987A\u5229\u4E4B\u540E",
    shortAnswer: "\u8FDE\u7EED\u987A\u5229\u5BB9\u6613\u8BA9\u4EBA\u4F4E\u4F30\u968F\u673A\u6027\u3002",
    reflectionQuestion: "\u4F60\u662F\u5426\u628A\u8FD0\u6C14\u5F53\u6210\u4E86\u80FD\u529B\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-066",
    title: "\u5BB3\u6015\u9519\u8FC7",
    shortAnswer: "\u673A\u4F1A\u611F\u8D8A\u5F3A\uFF0C\u6838\u5BF9\u8D8A\u5BB9\u6613\u88AB\u8DF3\u8FC7\u3002",
    reflectionQuestion: "\u5982\u679C\u5B83\u6D88\u5931\uFF0C\u4F60\u771F\u6B63\u5931\u53BB\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-067",
    title: "\u75B2\u60EB\u51B3\u7B56",
    shortAnswer: "\u75B2\u60EB\u4F1A\u7F29\u77ED\u601D\u8003\u8DEF\u5F84\u3002",
    reflectionQuestion: "\u73B0\u5728\u662F\u5426\u9002\u5408\u505A\u590D\u6742\u5224\u65AD\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-068",
    title: "\u7FA4\u4F53\u6E29\u5EA6",
    shortAnswer: "\u70ED\u95F9\u4F1A\u8BA9\u4E2A\u4EBA\u786E\u4FE1\u611F\u5347\u9AD8\u3002",
    reflectionQuestion: "\u79BB\u5F00\u7FA4\u804A\u540E\u7406\u7531\u8FD8\u6210\u7ACB\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-069",
    title: "\u540E\u6094\u9884\u6F14",
    shortAnswer: "\u4E3A\u4E86\u907F\u514D\u540E\u6094\uFF0C\u53EF\u80FD\u5236\u9020\u66F4\u591A\u540E\u6094\u3002",
    reflectionQuestion: "\u4F60\u5728\u4F18\u5316\u7ED3\u679C\u8FD8\u662F\u9003\u907F\u611F\u53D7\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-070",
    title: "\u8EAB\u4EFD\u89E3\u7ED1",
    shortAnswer: "\u4E00\u6B21\u7ED3\u679C\u4E0D\u80FD\u5B9A\u4E49\u5224\u65AD\u8005\u672C\u8EAB\u3002",
    reflectionQuestion: "\u4F60\u662F\u5426\u628A\u7ED3\u679C\u5F53\u6210\u81EA\u6211\u8BC4\u4EF7\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-071",
    title: "\u5141\u8BB8\u4E0D\u9002",
    shortAnswer: "\u4E0D\u9002\u4E0D\u4E00\u5B9A\u9700\u8981\u7ACB\u523B\u88AB\u884C\u52A8\u6D88\u9664\u3002",
    reflectionQuestion: "\u80FD\u5426\u8BA9\u8FD9\u79CD\u611F\u53D7\u505C\u7559\u5341\u5206\u949F\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-072",
    title: "\u6062\u590D\u5E73\u9759",
    shortAnswer: "\u5E73\u9759\u4E0D\u662F\u7ED3\u8BBA\uFF0C\u800C\u662F\u5224\u65AD\u7684\u8D77\u70B9\u3002",
    reflectionQuestion: "\u4EC0\u4E48\u6761\u4EF6\u4E0B\u4F60\u4F1A\u66F4\u5E73\u9759\uFF1F",
    boundary: "\u7528\u4E8E\u60C5\u7EEA\u89C9\u5BDF\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6295\u8D44\u884C\u52A8\u3002",
    category: "emotion",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-073",
    title: "\u89C4\u5219\u5728\u524D",
    shortAnswer: "\u4E8B\u524D\u89C4\u5219\u6BD4\u4E8B\u540E\u89E3\u91CA\u66F4\u53EF\u4FE1\u3002",
    reflectionQuestion: "\u89C4\u5219\u662F\u5728\u7ED3\u679C\u51FA\u73B0\u524D\u5199\u4E0B\u7684\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-074",
    title: "\u6761\u4EF6\u6E05\u695A",
    shortAnswer: "\u6A21\u7CCA\u6761\u4EF6\u4F1A\u7ED9\u51B2\u52A8\u7559\u4E0B\u7A7A\u95F4\u3002",
    reflectionQuestion: "\u884C\u52A8\u4E0E\u505C\u6B62\u6761\u4EF6\u8DB3\u591F\u6E05\u695A\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-075",
    title: "\u4E00\u6B21\u4E00\u95EE",
    shortAnswer: "\u95EE\u9898\u8D8A\u805A\u7126\uFF0C\u7B54\u6848\u8D8A\u53EF\u68C0\u9A8C\u3002",
    reflectionQuestion: "\u4F60\u73B0\u5728\u771F\u6B63\u8981\u89E3\u51B3\u54EA\u4E00\u4E2A\u95EE\u9898\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-076",
    title: "\u7559\u75D5",
    shortAnswer: "\u8BB0\u5F55\u80FD\u51CF\u5C11\u8BB0\u5FC6\u5BF9\u5386\u53F2\u7684\u6539\u5199\u3002",
    reflectionQuestion: "\u4F9D\u636E\u548C\u65F6\u95F4\u662F\u5426\u5DF2\u7ECF\u8BB0\u5F55\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-077",
    title: "\u7B49\u5F85\u6761\u4EF6",
    shortAnswer: "\u8010\u5FC3\u4E0D\u662F\u505C\u6EDE\uFF0C\u800C\u662F\u5C0A\u91CD\u6761\u4EF6\u3002",
    reflectionQuestion: "\u5173\u952E\u6761\u4EF6\u5DF2\u7ECF\u6EE1\u8DB3\u4E86\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-078",
    title: "\u51CF\u5C11\u4F8B\u5916",
    shortAnswer: "\u6BCF\u4E2A\u4E34\u65F6\u4F8B\u5916\u90FD\u4F1A\u524A\u5F31\u89C4\u5219\u3002",
    reflectionQuestion: "\u8FD9\u6B21\u4E3A\u4F55\u9700\u8981\u6210\u4E3A\u4F8B\u5916\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-079",
    title: "\u8FC7\u7A0B\u4F18\u5148",
    shortAnswer: "\u53EF\u91CD\u590D\u7684\u8FC7\u7A0B\u6BD4\u5355\u6B21\u7ED3\u679C\u91CD\u8981\u3002",
    reflectionQuestion: "\u8FD9\u5957\u8FC7\u7A0B\u4E0B\u6B21\u8FD8\u80FD\u4F7F\u7528\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-080",
    title: "\u68C0\u67E5\u51B2\u7A81",
    shortAnswer: "\u76F8\u4E92\u51B2\u7A81\u7684\u89C4\u5219\u65E0\u6CD5\u63D0\u4F9B\u8FB9\u754C\u3002",
    reflectionQuestion: "\u73B0\u6709\u89C4\u5219\u4E4B\u95F4\u6709\u77DB\u76FE\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-081",
    title: "\u8BBE\u7F6E\u590D\u76D8",
    shortAnswer: "\u6CA1\u6709\u590D\u76D8\u65E5\u671F\uFF0C\u5047\u8BBE\u5BB9\u6613\u65E0\u9650\u5EF6\u957F\u3002",
    reflectionQuestion: "\u4F55\u65F6\u91CD\u65B0\u68C0\u67E5\u8FD9\u9879\u5224\u65AD\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-082",
    title: "\u505C\u6B62\u52A0\u7801\u89E3\u91CA",
    shortAnswer: "\u89E3\u91CA\u8D8A\u591A\uFF0C\u4E0D\u4EE3\u8868\u7406\u7531\u8D8A\u5F3A\u3002",
    reflectionQuestion: "\u6838\u5FC3\u7406\u7531\u80FD\u5426\u7528\u4E09\u53E5\u8BDD\u8BF4\u6E05\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-083",
    title: "\u5C0A\u91CD\u672A\u77E5",
    shortAnswer: "\u7EAA\u5F8B\u4E5F\u5305\u62EC\u627F\u8BA4\u65E0\u6CD5\u5224\u65AD\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u90E8\u5206\u73B0\u5728\u786E\u5B9E\u4E0D\u77E5\u9053\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-084",
    title: "\u4E00\u81F4\u6267\u884C",
    shortAnswer: "\u540C\u6837\u6761\u4EF6\u5E94\u63A5\u53D7\u540C\u6837\u68C0\u9A8C\u3002",
    reflectionQuestion: "\u4F60\u662F\u5426\u56E0\u7ED3\u679C\u4E0D\u540C\u800C\u6539\u53D8\u6807\u51C6\uFF1F",
    boundary: "\u7528\u4E8E\u51B3\u7B56\u7EAA\u5F8B\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u5177\u4F53\u4EA4\u6613\u6B65\u9AA4\u3002",
    category: "discipline",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-085",
    title: "\u6807\u9898\u4E4B\u5916",
    shortAnswer: "\u6807\u9898\u8D1F\u8D23\u5438\u5F15\u6CE8\u610F\uFF0C\u4E0D\u8D1F\u8D23\u5B8C\u6574\u8868\u8FBE\u3002",
    reflectionQuestion: "\u6B63\u6587\u548C\u539F\u59CB\u6750\u6599\u8BF4\u4E86\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-086",
    title: "\u6765\u6E90\u94FE\u6761",
    shortAnswer: "\u591A\u6B21\u8F6C\u8FF0\u4F1A\u8BA9\u7EC6\u8282\u9010\u6B65\u53D8\u5F62\u3002",
    reflectionQuestion: "\u80FD\u8FFD\u6EAF\u5230\u6700\u521D\u6765\u6E90\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-087",
    title: "\u53D1\u5E03\u65F6\u95F4",
    shortAnswer: "\u65E7\u5185\u5BB9\u53EF\u80FD\u88AB\u5305\u88C5\u6210\u65B0\u6D88\u606F\u3002",
    reflectionQuestion: "\u4E8B\u4EF6\u548C\u53D1\u5E03\u5206\u522B\u53D1\u751F\u5728\u4F55\u65F6\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-088",
    title: "\u4E8B\u5B9E\u89C2\u70B9",
    shortAnswer: "\u4E8B\u5B9E\u4E0E\u8BC4\u8BBA\u6DF7\u5728\u4E00\u8D77\u65F6\u8981\u5206\u5F00\u8BFB\u3002",
    reflectionQuestion: "\u54EA\u53E5\u662F\u4E8B\u5B9E\uFF0C\u54EA\u53E5\u662F\u5224\u65AD\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-089",
    title: "\u622A\u56FE\u8FB9\u754C",
    shortAnswer: "\u622A\u56FE\u4E4B\u5916\u5E38\u5E38\u8FD8\u6709\u5FC5\u8981\u4E0A\u4E0B\u6587\u3002",
    reflectionQuestion: "\u5B8C\u6574\u9875\u9762\u5305\u542B\u54EA\u4E9B\u9650\u5B9A\u6761\u4EF6\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-090",
    title: "\u70ED\u5EA6\u504F\u5DEE",
    shortAnswer: "\u4F20\u64AD\u66F4\u5E7F\uFF0C\u4E0D\u4EE3\u8868\u66F4\u63A5\u8FD1\u4E8B\u5B9E\u3002",
    reflectionQuestion: "\u70ED\u5EA6\u662F\u5426\u66FF\u4EE3\u4E86\u8BC1\u636E\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-091",
    title: "\u533F\u540D\u6D88\u606F",
    shortAnswer: "\u65E0\u6CD5\u9A8C\u8BC1\u7684\u6765\u6E90\u9700\u8981\u66F4\u4F4E\u6743\u91CD\u3002",
    reflectionQuestion: "\u8FD9\u6761\u6D88\u606F\u5982\u4F55\u88AB\u72EC\u7ACB\u9A8C\u8BC1\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-092",
    title: "\u6570\u5B57\u5B8C\u6574",
    shortAnswer: "\u5B64\u7ACB\u6570\u5B57\u7F3A\u5C11\u53E3\u5F84\u548C\u6BD4\u8F83\u3002",
    reflectionQuestion: "\u5206\u6BCD\u3001\u533A\u95F4\u4E0E\u57FA\u51C6\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-093",
    title: "\u60C5\u7EEA\u63AA\u8F9E",
    shortAnswer: "\u5F3A\u70C8\u63AA\u8F9E\u4F1A\u653E\u5927\u786E\u5B9A\u6027\u611F\u53D7\u3002",
    reflectionQuestion: "\u53BB\u6389\u5F62\u5BB9\u8BCD\u540E\u8FD8\u5269\u4EC0\u4E48\u4E8B\u5B9E\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-094",
    title: "\u91CD\u590D\u56DE\u58F0",
    shortAnswer: "\u591A\u4E2A\u8F6C\u53D1\u53EF\u80FD\u53EA\u6709\u4E00\u4E2A\u539F\u59CB\u6765\u6E90\u3002",
    reflectionQuestion: "\u8FD9\u4E9B\u8BF4\u6CD5\u5F7C\u6B64\u771F\u7684\u72EC\u7ACB\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-095",
    title: "\u53CA\u65F6\u7EA0\u9519",
    shortAnswer: "\u53EF\u9760\u6765\u6E90\u4E5F\u53EF\u80FD\u4FEE\u8BA2\u5185\u5BB9\u3002",
    reflectionQuestion: "\u662F\u5426\u67E5\u770B\u8FC7\u540E\u7EED\u66F4\u6B63\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-096",
    title: "\u4FE1\u606F\u996E\u98DF",
    shortAnswer: "\u6301\u7EED\u5237\u65B0\u4F1A\u964D\u4F4E\u7B5B\u9009\u8D28\u91CF\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u6765\u6E90\u503C\u5F97\u56FA\u5B9A\u4FDD\u7559\uFF1F",
    boundary: "\u7528\u4E8E\u4FE1\u606F\u7D20\u517B\u6559\u80B2\uFF0C\u4E0D\u8BA4\u53EF\u6216\u5426\u5B9A\u4EFB\u4F55\u5E02\u573A\u4F20\u95FB\u3002",
    category: "information",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-097",
    title: "\u6574\u4F53\u89C6\u89D2",
    shortAnswer: "\u5355\u4E00\u90E8\u5206\u4E0D\u80FD\u4EE3\u8868\u6574\u4F53\u98CE\u9669\u3002",
    reflectionQuestion: "\u5B83\u5728\u6574\u4F53\u4E2D\u627F\u62C5\u4EC0\u4E48\u89D2\u8272\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-098",
    title: "\u91CD\u590D\u66B4\u9732",
    shortAnswer: "\u4E0D\u540C\u540D\u79F0\u53EF\u80FD\u5BF9\u5E94\u76F8\u4F3C\u9A71\u52A8\u3002",
    reflectionQuestion: "\u662F\u5426\u5B58\u5728\u91CD\u590D\u7684\u98CE\u9669\u6765\u6E90\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-099",
    title: "\u76EE\u6807\u5339\u914D",
    shortAnswer: "\u7EC4\u5408\u9996\u5148\u670D\u52A1\u4E8E\u751F\u6D3B\u76EE\u6807\u3002",
    reflectionQuestion: "\u5F53\u524D\u7ED3\u6784\u4ECD\u5339\u914D\u539F\u76EE\u6807\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-100",
    title: "\u5206\u6563\u76EE\u7684",
    shortAnswer: "\u5206\u6563\u662F\u4E3A\u4E86\u7BA1\u7406\u672A\u77E5\uFF0C\u4E0D\u662F\u6536\u96C6\u6570\u91CF\u3002",
    reflectionQuestion: "\u65B0\u589E\u90E8\u5206\u5E26\u6765\u65B0\u7684\u98CE\u9669\u6765\u6E90\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-101",
    title: "\u73B0\u91D1\u9700\u6C42",
    shortAnswer: "\u672A\u6765\u7528\u6B3E\u9700\u8981\u63D0\u524D\u8FDB\u5165\u89C6\u91CE\u3002",
    reflectionQuestion: "\u8FD1\u671F\u6709\u54EA\u4E9B\u786E\u5B9A\u7684\u8D44\u91D1\u9700\u6C42\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-102",
    title: "\u7EF4\u62A4\u96BE\u5EA6",
    shortAnswer: "\u96BE\u4EE5\u7EF4\u62A4\u7684\u590D\u6742\u5EA6\u4F1A\u53D8\u6210\u98CE\u9669\u3002",
    reflectionQuestion: "\u4F60\u80FD\u6301\u7EED\u7406\u89E3\u6BCF\u4E2A\u90E8\u5206\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-103",
    title: "\u518D\u5E73\u8861\u539F\u56E0",
    shortAnswer: "\u7ED3\u6784\u8C03\u6574\u5E94\u6765\u81EA\u76EE\u6807\u4E0E\u8FB9\u754C\u53D8\u5316\u3002",
    reflectionQuestion: "\u53D8\u5316\u6765\u81EA\u8BA1\u5212\u8FD8\u662F\u8FD1\u671F\u611F\u53D7\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-104",
    title: "\u96C6\u4E2D\u7406\u7531",
    shortAnswer: "\u96C6\u4E2D\u9700\u8981\u66F4\u9AD8\u7684\u7406\u89E3\u4E0E\u627F\u53D7\u80FD\u529B\u3002",
    reflectionQuestion: "\u4F60\u80FD\u6E05\u695A\u8BF4\u660E\u96C6\u4E2D\u4F9D\u636E\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-105",
    title: "\u98CE\u9669\u9884\u7B97",
    shortAnswer: "\u6BCF\u4EFD\u98CE\u9669\u90FD\u5E94\u6709\u660E\u786E\u7528\u9014\u3002",
    reflectionQuestion: "\u6700\u5927\u538B\u529B\u662F\u5426\u5F71\u54CD\u6838\u5FC3\u751F\u6D3B\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-106",
    title: "\u671F\u9650\u5206\u5C42",
    shortAnswer: "\u4E0D\u540C\u7528\u9014\u9700\u8981\u4E0D\u540C\u65F6\u95F4\u5B89\u6392\u3002",
    reflectionQuestion: "\u5404\u90E8\u5206\u7684\u4F7F\u7528\u65F6\u95F4\u6E05\u695A\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-107",
    title: "\u76F8\u5173\u53D8\u5316",
    shortAnswer: "\u76F8\u5173\u5173\u7CFB\u4F1A\u968F\u73AF\u5883\u6539\u53D8\u3002",
    reflectionQuestion: "\u538B\u529B\u60C5\u5F62\u4E0B\u5206\u6563\u4ECD\u6709\u6548\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-108",
    title: "\u4FDD\u6301\u7B80\u5355",
    shortAnswer: "\u80FD\u89E3\u91CA\u7684\u7ED3\u6784\u66F4\u5BB9\u6613\u88AB\u575A\u6301\u3002",
    reflectionQuestion: "\u80FD\u5426\u5220\u53BB\u4E00\u4E2A\u4E0D\u5FC5\u8981\u7684\u590D\u6742\u70B9\uFF1F",
    boundary: "\u7528\u4E8E\u7EC4\u5408\u89C2\u5FF5\u6559\u80B2\uFF0C\u4E0D\u63D0\u4F9B\u914D\u7F6E\u6BD4\u4F8B\u6216\u4EA7\u54C1\u63A8\u8350\u3002",
    category: "portfolio",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-109",
    title: "\u91CD\u5EFA\u73B0\u573A",
    shortAnswer: "\u590D\u76D8\u8981\u56DE\u5230\u5F53\u65F6\u53EF\u89C1\u7684\u4FE1\u606F\u3002",
    reflectionQuestion: "\u5F53\u65F6\u5B9E\u9645\u77E5\u9053\u54EA\u4E9B\u4E8B\u5B9E\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-110",
    title: "\u8FC7\u7A0B\u8BC4\u5206",
    shortAnswer: "\u8FC7\u7A0B\u8D28\u91CF\u4E0D\u5E94\u53EA\u7531\u7ED3\u679C\u51B3\u5B9A\u3002",
    reflectionQuestion: "\u5982\u679C\u7ED3\u679C\u76F8\u53CD\uFF0C\u4F60\u5982\u4F55\u8BC4\u4EF7\u8FC7\u7A0B\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-111",
    title: "\u5BFB\u627E\u91CD\u590D",
    shortAnswer: "\u91CD\u590D\u51FA\u73B0\u7684\u95EE\u9898\u66F4\u503C\u5F97\u4F18\u5148\u4FEE\u6B63\u3002",
    reflectionQuestion: "\u8FD1\u671F\u6709\u54EA\u79CD\u884C\u4E3A\u53CD\u590D\u51FA\u73B0\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-112",
    title: "\u6700\u5C0F\u6539\u8FDB",
    shortAnswer: "\u5C0F\u800C\u660E\u786E\u7684\u6539\u8FDB\u66F4\u5BB9\u6613\u575A\u6301\u3002",
    reflectionQuestion: "\u4E0B\u6B21\u53EA\u6539\u53D8\u4E00\u4EF6\u4E8B\uFF0C\u4F1A\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-113",
    title: "\u8BB0\u5F55\u7F3A\u53E3",
    shortAnswer: "\u6CA1\u6709\u8BB0\u5F55\u7684\u90E8\u5206\u65E0\u6CD5\u53EF\u9760\u590D\u76D8\u3002",
    reflectionQuestion: "\u54EA\u9879\u5173\u952E\u4FE1\u606F\u6CA1\u6709\u7559\u4E0B\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-114",
    title: "\u66F4\u65B0\u5047\u8BBE",
    shortAnswer: "\u65B0\u4E8B\u5B9E\u51FA\u73B0\u540E\uFF0C\u65E7\u5047\u8BBE\u9700\u8981\u91CD\u5BA1\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u5047\u8BBE\u88AB\u652F\u6301\u6216\u524A\u5F31\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-115",
    title: "\u7ED3\u679C\u62C6\u5206",
    shortAnswer: "\u7ED3\u679C\u901A\u5E38\u6765\u81EA\u80FD\u529B\u3001\u73AF\u5883\u4E0E\u968F\u673A\u6027\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u90E8\u5206\u6682\u65F6\u65E0\u6CD5\u533A\u5206\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-116",
    title: "\u8BC6\u522B\u501F\u53E3",
    shortAnswer: "\u4E8B\u540E\u7406\u7531\u5E38\u6BD4\u4E8B\u524D\u7406\u7531\u66F4\u5B8C\u6574\u3002",
    reflectionQuestion: "\u8FD9\u4E2A\u7406\u7531\u5F53\u65F6\u5DF2\u7ECF\u5B58\u5728\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-117",
    title: "\u590D\u76D8\u8282\u594F",
    shortAnswer: "\u8FC7\u5BC6\u590D\u76D8\u5BB9\u6613\u88AB\u77ED\u671F\u6CE2\u52A8\u7275\u5F15\u3002",
    reflectionQuestion: "\u68C0\u67E5\u9891\u7387\u4E0E\u76EE\u6807\u671F\u9650\u5339\u914D\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-118",
    title: "\u4FDD\u7559\u6709\u6548",
    shortAnswer: "\u590D\u76D8\u4E0D\u53EA\u627E\u9519\uFF0C\u4E5F\u8981\u4FDD\u7559\u597D\u8FC7\u7A0B\u3002",
    reflectionQuestion: "\u54EA\u9879\u7EAA\u5F8B\u503C\u5F97\u7EE7\u7EED\u4FDD\u6301\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-119",
    title: "\u5173\u6CE8\u51B3\u7B56",
    shortAnswer: "\u53EF\u63A7\u7684\u662F\u8FC7\u7A0B\uFF0C\u4E0D\u662F\u6BCF\u6B21\u7ED3\u679C\u3002",
    reflectionQuestion: "\u4E0B\u4E00\u6B21\u53EF\u4EE5\u63A7\u5236\u54EA\u4E9B\u73AF\u8282\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-120",
    title: "\u5F62\u6210\u6E05\u5355",
    shortAnswer: "\u7A33\u5B9A\u6E05\u5355\u80FD\u51CF\u5C11\u538B\u529B\u4E0B\u7684\u9057\u6F0F\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u6838\u5BF9\u9879\u5E94\u56FA\u5B9A\u4E0B\u6765\uFF1F",
    boundary: "\u7528\u4E8E\u4E2A\u4EBA\u51B3\u7B56\u590D\u76D8\uFF0C\u4E0D\u751F\u6210\u4E1A\u7EE9\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-121",
    title: "\u6982\u7387\u8BED\u8A00",
    shortAnswer: "\u4E0D\u786E\u5B9A\u7684\u4E16\u754C\u9700\u8981\u6982\u7387\u800C\u975E\u65AD\u8A00\u3002",
    reflectionQuestion: "\u4F60\u7684\u786E\u4FE1\u7A0B\u5EA6\u80FD\u5426\u66F4\u51C6\u786E\u8868\u8FBE\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-122",
    title: "\u8303\u56F4\u800C\u975E\u70B9",
    shortAnswer: "\u5355\u4E00\u70B9\u4F4D\u5BB9\u6613\u5236\u9020\u865A\u5047\u7684\u7CBE\u786E\u3002",
    reflectionQuestion: "\u53EF\u80FD\u7ED3\u679C\u7684\u8303\u56F4\u6709\u591A\u5BBD\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-123",
    title: "\u60C5\u666F\u601D\u8003",
    shortAnswer: "\u591A\u79CD\u60C5\u666F\u5E76\u5B58\uFF0C\u6BD4\u5355\u4E00\u8DEF\u5F84\u66F4\u771F\u5B9E\u3002",
    reflectionQuestion: "\u81F3\u5C11\u8FD8\u6709\u54EA\u4E24\u79CD\u53EF\u80FD\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-124",
    title: "\u66F4\u65B0\u800C\u975E\u56FA\u5B88",
    shortAnswer: "\u65B0\u8BC1\u636E\u51FA\u73B0\u65F6\uFF0C\u8C03\u6574\u770B\u6CD5\u662F\u7406\u6027\u3002",
    reflectionQuestion: "\u4EC0\u4E48\u65B0\u8BC1\u636E\u503C\u5F97\u66F4\u65B0\u5224\u65AD\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-125",
    title: "\u672A\u77E5\u672A\u77E5",
    shortAnswer: "\u65E0\u6CD5\u5217\u51FA\u7684\u98CE\u9669\u4ECD\u7136\u5B58\u5728\u3002",
    reflectionQuestion: "\u4F60\u4E3A\u610F\u5916\u4FDD\u7559\u4E86\u4EC0\u4E48\u4F59\u5730\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-126",
    title: "\u7F6E\u4FE1\u6765\u6E90",
    shortAnswer: "\u719F\u6089\u611F\u5E38\u88AB\u8BEF\u8BA4\u4E3A\u786E\u5B9A\u6027\u3002",
    reflectionQuestion: "\u786E\u4FE1\u6765\u81EA\u8BC1\u636E\u8FD8\u662F\u91CD\u590D\u63A5\u89E6\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-127",
    title: "\u53EF\u9006\u7A0B\u5EA6",
    shortAnswer: "\u4E0D\u53EF\u9006\u51B3\u5B9A\u9700\u8981\u66F4\u9AD8\u8BC1\u636E\u95E8\u69DB\u3002",
    reflectionQuestion: "\u8FD9\u4E2A\u51B3\u5B9A\u6709\u591A\u5BB9\u6613\u64A4\u56DE\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-128",
    title: "\u8BEF\u5DEE\u7A7A\u95F4",
    shortAnswer: "\u4F30\u8BA1\u5FC5\u7136\u5E26\u6709\u8BEF\u5DEE\u3002",
    reflectionQuestion: "\u7ED3\u8BBA\u5BF9\u8BEF\u5DEE\u6709\u591A\u654F\u611F\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-129",
    title: "\u4E0D\u6025\u5B9A\u8BBA",
    shortAnswer: "\u6682\u4E0D\u5224\u65AD\u4E5F\u662F\u8BDA\u5B9E\u7B54\u6848\u3002",
    reflectionQuestion: "\u73B0\u6709\u4FE1\u606F\u8DB3\u4EE5\u5F62\u6210\u7ED3\u8BBA\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-130",
    title: "\u9884\u671F\u4E4B\u5916",
    shortAnswer: "\u73B0\u5B9E\u7ECF\u5E38\u8D70\u51FA\u672A\u5217\u51FA\u7684\u8DEF\u5F84\u3002",
    reflectionQuestion: "\u54EA\u4E2A\u5047\u8BBE\u6700\u9650\u5236\u4F60\u7684\u60F3\u8C61\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-131",
    title: "\u957F\u671F\u4E0D\u786E\u5B9A",
    shortAnswer: "\u65F6\u95F4\u66F4\u957F\uFF0C\u4E0D\u4EE3\u8868\u4E0D\u786E\u5B9A\u6027\u6D88\u5931\u3002",
    reflectionQuestion: "\u54EA\u4E9B\u53D8\u91CF\u4F1A\u968F\u65F6\u95F4\u53D8\u5316\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-132",
    title: "\u8C26\u900A\u8FB9\u754C",
    shortAnswer: "\u6E05\u695A\u77E5\u9053\u4E0D\u77E5\u9053\u4EC0\u4E48\uFF0C\u662F\u5224\u65AD\u529B\u7684\u4E00\u90E8\u5206\u3002",
    reflectionQuestion: "\u4F60\u80FD\u5217\u51FA\u4E09\u9879\u672A\u77E5\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u7406\u89E3\u4E0D\u786E\u5B9A\u6027\uFF0C\u4E0D\u63D0\u4F9B\u884C\u60C5\u65B9\u5411\u5224\u65AD\u3002",
    category: "uncertainty",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-133",
    title: "\u751F\u6D3B\u4F18\u5148",
    shortAnswer: "\u8D26\u6237\u670D\u52A1\u4E8E\u751F\u6D3B\uFF0C\u800C\u4E0D\u662F\u76F8\u53CD\u3002",
    reflectionQuestion: "\u8FD9\u9879\u51B3\u5B9A\u4F1A\u5F71\u54CD\u65E5\u5E38\u751F\u6D3B\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-134",
    title: "\u7761\u7720\u4FE1\u53F7",
    shortAnswer: "\u6301\u7EED\u5931\u7720\u8BF4\u660E\u538B\u529B\u5DF2\u7ECF\u8D8A\u754C\u3002",
    reflectionQuestion: "\u6700\u8FD1\u7761\u7720\u662F\u5426\u53D7\u5230\u5F71\u54CD\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-135",
    title: "\u5BB6\u5EAD\u6C9F\u901A",
    shortAnswer: "\u5171\u540C\u751F\u6D3B\u9700\u8981\u5171\u540C\u7406\u89E3\u98CE\u9669\u3002",
    reflectionQuestion: "\u91CD\u8981\u5BB6\u4EBA\u4E86\u89E3\u76F8\u5173\u5B89\u6392\u5417\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-136",
    title: "\u65F6\u95F4\u6210\u672C",
    shortAnswer: "\u76EF\u5C4F\u65F6\u95F4\u4E5F\u662F\u5B9E\u9645\u6210\u672C\u3002",
    reflectionQuestion: "\u5B83\u5360\u7528\u4E86\u54EA\u4E9B\u66F4\u91CD\u8981\u7684\u65F6\u95F4\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-137",
    title: "\u5E94\u6025\u8FB9\u754C",
    shortAnswer: "\u5E94\u6025\u8D44\u6E90\u9996\u5148\u627F\u62C5\u751F\u6D3B\u4FDD\u969C\u3002",
    reflectionQuestion: "\u7A81\u53D1\u9700\u8981\u662F\u5426\u5DF2\u6709\u72EC\u7ACB\u5B89\u6392\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-138",
    title: "\u60C5\u7EEA\u5916\u6EA2",
    shortAnswer: "\u8D26\u6237\u538B\u529B\u53EF\u80FD\u6D41\u5411\u5DE5\u4F5C\u4E0E\u5173\u7CFB\u3002",
    reflectionQuestion: "\u538B\u529B\u6B63\u5728\u5F71\u54CD\u8C01\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-139",
    title: "\u8EAB\u4EFD\u591A\u5143",
    shortAnswer: "\u4E2A\u4EBA\u4EF7\u503C\u4E0D\u7531\u8D26\u6237\u7ED3\u679C\u5B9A\u4E49\u3002",
    reflectionQuestion: "\u79BB\u5F00\u5E02\u573A\uFF0C\u4F60\u8FD8\u73CD\u89C6\u54EA\u4E9B\u8EAB\u4EFD\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-140",
    title: "\u4F11\u606F\u8BB8\u53EF",
    shortAnswer: "\u6682\u505C\u5173\u6CE8\u4E0D\u4F1A\u524A\u5F31\u957F\u671F\u76EE\u6807\u3002",
    reflectionQuestion: "\u4F60\u591A\u4E45\u6CA1\u6709\u5B8C\u6574\u4F11\u606F\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-141",
    title: "\u6C42\u52A9\u65F6\u673A",
    shortAnswer: "\u72EC\u81EA\u627F\u53D7\u4E0D\u662F\u6210\u719F\u7684\u8BC1\u660E\u3002",
    reflectionQuestion: "\u662F\u5426\u9700\u8981\u53EF\u4FE1\u7684\u4EBA\u4E00\u8D77\u8BA8\u8BBA\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-142",
    title: "\u4E13\u4E1A\u8FB9\u754C",
    shortAnswer: "\u590D\u6742\u95EE\u9898\u9700\u8981\u5339\u914D\u4E13\u4E1A\u80FD\u529B\u3002",
    reflectionQuestion: "\u4F55\u65F6\u5E94\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-143",
    title: "\u4FE1\u606F\u5173\u95ED",
    shortAnswer: "\u8BBE\u5B9A\u79BB\u7EBF\u65F6\u95F4\u80FD\u4FDD\u62A4\u6CE8\u610F\u529B\u3002",
    reflectionQuestion: "\u4ECA\u5929\u4F55\u65F6\u7ED3\u675F\u4FE1\u606F\u8F93\u5165\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-144",
    title: "\u56DE\u5230\u5F53\u4E0B",
    shortAnswer: "\u751F\u6D3B\u4E0D\u4F1A\u7B49\u5F85\u8D26\u6237\u6062\u590D\u5E73\u9759\u3002",
    reflectionQuestion: "\u6B64\u523B\u6700\u503C\u5F97\u6295\u5165\u7684\u4EBA\u548C\u4E8B\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u7528\u4E8E\u751F\u6D3B\u4E0E\u6295\u8D44\u8FB9\u754C\u6559\u80B2\uFF1B\u5982\u6709\u9700\u8981\uFF0C\u8BF7\u54A8\u8BE2\u6301\u724C\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "1.0.0",
    reviewStatus: "approved"
  }
];

// cloudfunctions/draw/core.ts
var CARDS = cards_generated_default;
var EVENT_NAMES = [
  "home_view",
  "draw_start",
  "draw_complete",
  "share_initiated",
  "share_landing_view",
  "shared_user_draw_start",
  "favorite_add",
  "favorite_remove",
  "restore_failed",
  "about_view"
];
var safePayloadKeys = /* @__PURE__ */ new Set([
  "drawId",
  "cardId",
  "theme",
  "attribution",
  "parentDrawId",
  "interaction",
  "animationMs",
  "shareCopy"
]);
function approvedPool(offlineIds, theme) {
  const offline = new Set(offlineIds);
  return CARDS.filter(
    (card) => card.reviewStatus === "approved" && !offline.has(card.id) && (!theme || card.category === theme)
  );
}
function assignExperiment(seed) {
  const bucket = (0, import_node_crypto.createHash)("sha256").update(seed).digest()[0];
  return {
    interaction: bucket % 2 === 0 ? "tap" : "hold",
    animationMs: bucket % 4 < 2 ? 500 : 1e3,
    shareCopy: bucket % 8 < 4 ? "a" : "b"
  };
}
function sanitizeText(value, maxLength) {
  if (typeof value !== "string") return void 0;
  const cleaned = value.replace(/[^a-zA-Z0-9_:/.-]/g, "").slice(0, maxLength);
  return cleaned || void 0;
}
function createDrawId() {
  return `d_${Date.now().toString(36)}_${(0, import_node_crypto.randomBytes)(12).toString("base64url")}`;
}
async function draw(repository2, input, random = Math.random) {
  const offlineIds = await repository2.getOfflineCardIds();
  const pool = approvedPool(offlineIds, input.theme);
  if (!pool.length) throw new Error("NO_APPROVED_CONTENT");
  const card = pool[Math.floor(random() * pool.length)];
  const drawId = createDrawId();
  const anonymousId = sanitizeText(input.anonymousId, 64) || drawId;
  const experiment = assignExperiment(anonymousId);
  const record = {
    drawId,
    cardId: card.id,
    createdAt: Date.now(),
    attribution: sanitizeText(input.attribution, 80),
    experiment
  };
  await repository2.saveDraw(record);
  return { drawId, card, experiment };
}
async function restore(repository2, drawIdInput) {
  const drawId = sanitizeText(drawIdInput, 80);
  if (!drawId || !drawId.startsWith("d_")) return null;
  const record = await repository2.getDraw(drawId);
  if (!record) return null;
  const offlineIds = await repository2.getOfflineCardIds();
  const card = approvedPool(offlineIds).find((item) => item.id === record.cardId);
  if (!card) return { drawId, unavailable: true, experiment: record.experiment };
  return { drawId, card, experiment: record.experiment };
}
async function captureEvent(repository2, input) {
  if (typeof input.name !== "string" || !EVENT_NAMES.includes(input.name)) {
    throw new Error("INVALID_EVENT");
  }
  const rawPayload = input.payload && typeof input.payload === "object" ? input.payload : {};
  const payload = {};
  for (const [key, value] of Object.entries(rawPayload)) {
    if (!safePayloadKeys.has(key)) continue;
    if (typeof value === "string") payload[key] = value.slice(0, 100);
    if (typeof value === "number" && Number.isFinite(value)) payload[key] = value;
    if (typeof value === "boolean") payload[key] = value;
  }
  await repository2.saveEvent({
    name: input.name,
    at: Date.now(),
    anonymousId: sanitizeText(input.anonymousId, 64) || "anonymous",
    payload
  });
  return { accepted: true };
}

// cloudfunctions/draw/index.ts
var cloud = require("wx-server-sdk");
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
var db = cloud.database();
var repository = {
  async saveDraw(record) {
    await db.collection("draws").add({ data: record });
  },
  async getDraw(drawId) {
    const result = await db.collection("draws").where({ drawId }).limit(1).get();
    return result.data[0] || null;
  },
  async saveEvent(record) {
    await db.collection("events").add({ data: record });
  },
  async getOfflineCardIds() {
    try {
      const result = await db.collection("content_config").doc("active").get();
      return Array.isArray(result.data.offlineCardIds) ? result.data.offlineCardIds : [];
    } catch {
      return [];
    }
  }
};
async function main(event, context) {
  const wxContext = cloud.getWXContext();
  const anonymousId = wxContext.OPENID || context.requestId || "anonymous";
  if (event.action === "draw") {
    return draw(repository, {
      theme: event.theme,
      attribution: event.attribution,
      anonymousId
    });
  }
  if (event.action === "restore") {
    return restore(repository, event.drawId);
  }
  if (event.action === "event") {
    return captureEvent(repository, {
      name: event.name,
      payload: event.payload,
      anonymousId
    });
  }
  throw new Error("INVALID_ACTION");
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  main
});

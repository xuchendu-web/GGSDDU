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
    title: "\u5148\u559D\u53E3\u6C34",
    shortAnswer: "\u7B54\u6848\u53C8\u4E0D\u4F1A\u8D81\u4F60\u559D\u6C34\u8DD1\u6389\u3002",
    reflectionQuestion: "\u5B83\u771F\u7684\u8D76\u65F6\u95F4\u5417\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-002",
    title: "\u95E8\u8FD8\u6CA1\u5F00",
    shortAnswer: "\u95E8\u8FD8\u6CA1\u5F00\uFF0C\u620F\u5DF2\u7ECF\u5F88\u8DB3\u4E86\u3002",
    reflectionQuestion: "\u8981\u4E0D\u8981\u5148\u5750\u4E0B\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-003",
    title: "\u65E9\u9910\u53D1\u8A00",
    shortAnswer: "\u7A7A\u7740\u809A\u5B50\u7684\u8C6A\u8A00\uFF0C\u5148\u6253\u4E2A\u6298\u3002",
    reflectionQuestion: "\u4F60\u5403\u65E9\u996D\u4E86\u5417\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-004",
    title: "\u95F9\u949F\u77E5\u9053",
    shortAnswer: "\u95F9\u949F\u8D1F\u8D23\u53EB\u9192\uFF0C\u4E0D\u8D1F\u8D23\u53EB\u5BF9\u3002",
    reflectionQuestion: "\u662F\u8C01\u8FD9\u4E48\u7740\u6025\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-005",
    title: "\u4ECA\u5929\u5F88\u957F",
    shortAnswer: "\u4E5D\u70B9\u7684\u7B03\u5B9A\uFF0C\u4E0B\u5348\u672A\u5FC5\u8BA4\u8BC6\u3002",
    reflectionQuestion: "\u8981\u4E0D\u7ED9\u5B83\u7559\u70B9\u4F59\u5730\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-006",
    title: "\u5148\u522B\u914D\u4E50",
    shortAnswer: "\u97F3\u4E50\u4E00\u8D77\uFF0C\u666E\u901A\u5267\u60C5\u4E5F\u50CF\u5927\u7247\u3002",
    reflectionQuestion: "\u662F\u4E0D\u662F\u6C14\u6C1B\u5230\u4E86\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-007",
    title: "\u624B\u901F\u51A0\u519B",
    shortAnswer: "\u5FEB\u4E0D\u4E00\u5B9A\u8D62\uFF0C\u4E5F\u53EF\u80FD\u53EA\u662F\u5FEB\u3002",
    reflectionQuestion: "\u6162\u4E00\u79D2\u4F1A\u600E\u6837\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-008",
    title: "\u5929\u6C14\u4E0D\u9519",
    shortAnswer: "\u5929\u6C14\u4E0D\u9519\uFF0C\u548C\u7B54\u6848\u5173\u7CFB\u4E0D\u5927\u3002",
    reflectionQuestion: "\u4F46\u5FC3\u60C5\u6709\u5173\u7CFB\u5417\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-009",
    title: "\u518D\u7728\u4E0B\u773C",
    shortAnswer: "\u6709\u4E9B\u673A\u4F1A\uFF0C\u7ECF\u5F97\u8D77\u4E00\u6B21\u7728\u773C\u3002",
    reflectionQuestion: "\u5B83\u8FD8\u5728\u5417\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-010",
    title: "\u5EA7\u4F4D\u8FD8\u5728",
    shortAnswer: "\u6CA1\u8D76\u4E0A\u524D\u6392\uFF0C\u4E5F\u80FD\u770B\u5B8C\u6574\u573A\u3002",
    reflectionQuestion: "\u4F60\u975E\u5F97\u5750\u7B2C\u4E00\u6392\u5417\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-011",
    title: "\u5148\u7A7F\u978B",
    shortAnswer: "\u8FDC\u65B9\u5F88\u8FDC\uFF0C\u978B\u5E26\u5012\u662F\u8FD1\u3002",
    reflectionQuestion: "\u773C\u524D\u54EA\u4EF6\u5C0F\u4E8B\u6CA1\u5F04\u597D\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-012",
    title: "\u6668\u95F4\u65B0\u95FB",
    shortAnswer: "\u65E9\u6D88\u606F\u5F88\u65B0\uFF0C\u672A\u5FC5\u5F88\u719F\u3002",
    reflectionQuestion: "\u8981\u4E0D\u8981\u7B49\u5B83\u81EA\u6211\u4ECB\u7ECD\uFF1F",
    boundary: "\u53EA\u662F\u968F\u624B\u4E00\u9875\uFF0C\u4E0D\u66FF\u4F60\u505A\u51B3\u5B9A\u3002",
    category: "preopen",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-013",
    title: "\u706F\u5173\u4E86",
    shortAnswer: "\u6563\u573A\u4EE5\u540E\uFF0C\u4E3B\u89D2\u4E5F\u8981\u5750\u5730\u94C1\u3002",
    reflectionQuestion: "\u4F60\u8FD8\u5728\u52A0\u620F\u5417\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-014",
    title: "\u4ECA\u65E5\u4EFD",
    shortAnswer: "\u4ECA\u5929\u5DF2\u7ECF\u5F88\u6EE1\uFF0C\u4E0D\u5FC5\u518D\u585E\u7ED3\u8BBA\u3002",
    reflectionQuestion: "\u80FD\u5148\u7A7A\u4E00\u683C\u5417\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-015",
    title: "\u56DE\u653E\u5361\u987F",
    shortAnswer: "\u8BB0\u5FC6\u81EA\u5E26\u526A\u8F91\uFF0C\u8FD8\u662F\u5BFC\u6F14\u7248\u3002",
    reflectionQuestion: "\u6F0F\u6389\u4E86\u54EA\u4E00\u5E55\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-016",
    title: "\u6210\u7EE9\u5355",
    shortAnswer: "\u4E00\u9053\u9898\u5BF9\u4E86\uFF0C\u4E0D\u7B49\u4E8E\u5B57\u5199\u5F97\u597D\u3002",
    reflectionQuestion: "\u8FC7\u7A0B\u7ECF\u5F97\u8D77\u91CD\u64AD\u5417\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-017",
    title: "\u4E0B\u73ED\u94C3",
    shortAnswer: "\u5C4F\u5E55\u4E0B\u73ED\u4E86\uFF0C\u4F60\u4E5F\u53EF\u4EE5\u3002",
    reflectionQuestion: "\u8FD8\u6709\u4EC0\u4E48\u975E\u60F3\u4E0D\u53EF\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-018",
    title: "\u665A\u996D\u91CD\u8981",
    shortAnswer: "\u665A\u996D\u51C9\u4E86\uFF0C\u6BD4\u6570\u5B57\u8BDA\u5B9E\u3002",
    reflectionQuestion: "\u5148\u7BA1\u54EA\u4E00\u4E2A\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-019",
    title: "\u4ECA\u65E5\u5929\u6C14",
    shortAnswer: "\u4E00\u5929\u50CF\u5929\u6C14\uFF0C\u522B\u6025\u7740\u5199\u6210\u6C14\u5019\u3002",
    reflectionQuestion: "\u660E\u5929\u4F1A\u8BA4\u8FD9\u53E5\u8BDD\u5417\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-020",
    title: "\u638C\u58F0\u6765\u6E90",
    shortAnswer: "\u987A\u5229\u7684\u65F6\u5019\uFF0C\u98CE\u4E5F\u4F1A\u9F13\u638C\u3002",
    reflectionQuestion: "\u54EA\u90E8\u5206\u662F\u98CE\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-021",
    title: "\u5931\u7269\u62DB\u9886",
    shortAnswer: "\u4ECA\u5929\u4E22\u7684\u4E5F\u8BB8\u53EA\u662F\u8010\u5FC3\u3002",
    reflectionQuestion: "\u8981\u4E0D\u8981\u53BB\u9886\u56DE\u6765\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-022",
    title: "\u5173\u706F\u4EE5\u540E",
    shortAnswer: "\u9ED1\u5C4F\u5F88\u5B89\u9759\uFF0C\u8111\u5185\u5F39\u5E55\u4E0D\u662F\u3002",
    reflectionQuestion: "\u8C01\u8FD8\u5728\u5237\u5C4F\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-023",
    title: "\u6700\u540E\u4E00\u53E5",
    shortAnswer: "\u6536\u5C3E\u592A\u7528\u529B\uFF0C\u50CF\u6CA1\u820D\u5F97\u7ED3\u675F\u3002",
    reflectionQuestion: "\u53E5\u53F7\u653E\u54EA\u513F\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-024",
    title: "\u660E\u5929\u518D\u8BF4",
    shortAnswer: "\u6709\u4E9B\u7B54\u6848\u7761\u4E00\u89C9\u4F1A\u81EA\u5DF1\u6539\u53E3\u3002",
    reflectionQuestion: "\u8BA9\u5B83\u7761\u5417\uFF1F",
    boundary: "\u53EA\u662F\u6536\u76D8\u540E\u7684\u4E00\u53E5\u95F2\u8BDD\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u6807\u7684\u3002",
    category: "close",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-025",
    title: "\u5468\u672B\u6A21\u5F0F",
    shortAnswer: "\u5468\u672B\u7684\u6570\u5B57\uFF0C\u6700\u597D\u4E5F\u7A7F\u62D6\u978B\u3002",
    reflectionQuestion: "\u8FD8\u8981\u8FD9\u4E48\u6B63\u5F0F\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-026",
    title: "\u67DC\u5B50\u6709\u70B9\u6EE1",
    shortAnswer: "\u4E1C\u897F\u591A\u4E86\uFF0C\u540D\u5B57\u5148\u4E92\u76F8\u5FD8\u8BB0\u3002",
    reflectionQuestion: "\u4F60\u90FD\u53EB\u5F97\u4E0A\u6765\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-027",
    title: "\u690D\u7269\u65F6\u95F4",
    shortAnswer: "\u6709\u4E9B\u53D8\u5316\uFF0C\u76EF\u7740\u53CD\u800C\u770B\u4E0D\u89C1\u3002",
    reflectionQuestion: "\u53BB\u7ED9\u82B1\u6D47\u6C34\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-028",
    title: "\u5927\u626B\u9664",
    shortAnswer: "\u820D\u4E0D\u5F97\u6254\u7684\u76D2\u5B50\uFF0C\u901A\u5E38\u6700\u5360\u5730\u65B9\u3002",
    reflectionQuestion: "\u54EA\u4E2A\u76D2\u5B50\u662F\u7A7A\u7684\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-029",
    title: "\u62FC\u56FE\u80CC\u9762",
    shortAnswer: "\u7FFB\u8FC7\u6765\u4E00\u770B\uFF0C\u5927\u5BB6\u90FD\u4E00\u4E2A\u989C\u8272\u3002",
    reflectionQuestion: "\u771F\u7684\u4E0D\u4E00\u6837\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-030",
    title: "\u5468\u4E00\u8FD8\u8FDC",
    shortAnswer: "\u79BB\u5468\u4E00\u8FD8\u6709\u4E24\u987F\u65E9\u996D\u3002",
    reflectionQuestion: "\u975E\u5F97\u73B0\u5728\u60F3\u5B8C\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-031",
    title: "\u6C99\u53D1\u610F\u89C1",
    shortAnswer: "\u6C99\u53D1\u8BA4\u4E3A\uFF0C\u5750\u4E0B\u518D\u8BF4\u3002",
    reflectionQuestion: "\u4F60\u540C\u610F\u6C99\u53D1\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-032",
    title: "\u8FDC\u770B\u4E00\u4E0B",
    shortAnswer: "\u9000\u4E09\u6B65\uFF0C\u7EC6\u8282\u7EC8\u4E8E\u80AF\u95ED\u5634\u3002",
    reflectionQuestion: "\u73B0\u5728\u770B\u89C1\u4EC0\u4E48\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-033",
    title: "\u8863\u67DC\u903B\u8F91",
    shortAnswer: "\u5E38\u7A7F\u7684\u6CA1\u51E0\u4EF6\uFF0C\u6302\u7740\u7684\u5F88\u70ED\u95F9\u3002",
    reflectionQuestion: "\u54EA\u4EF6\u53EA\u662F\u820D\u4E0D\u5F97\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-034",
    title: "\u65E5\u5386\u7FFB\u9762",
    shortAnswer: "\u4E00\u5468\u5F88\u77ED\uFF0C\u6545\u4E8B\u4E0D\u7528\u5199\u5B8C\u3002",
    reflectionQuestion: "\u4E0B\u4E00\u9875\u7559\u7ED9\u4EC0\u4E48\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-035",
    title: "\u5468\u672B\u6765\u4FE1",
    shortAnswer: "\u5BC4\u4FE1\u7684\u4EBA\u662F\u5468\u4E00\u7684\u4F60\u3002",
    reflectionQuestion: "\u4ED6\u4F1A\u5199\u4EC0\u4E48\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-036",
    title: "\u6682\u505C\u8425\u4E1A",
    shortAnswer: "\u8111\u5B50\u4E5F\u6709\u6253\u70CA\u65F6\u95F4\u3002",
    reflectionQuestion: "\u95E8\u724C\u6302\u4E0A\u4E86\u5417\uFF1F",
    boundary: "\u5468\u672B\u968F\u4FBF\u7FFB\u7FFB\uFF0C\u4E0D\u6784\u6210\u4EFB\u4F55\u5EFA\u8BAE\u3002",
    category: "weekend",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-037",
    title: "\u58F0\u97F3\u5F88\u5927",
    shortAnswer: "\u6269\u97F3\u5668\u5F88\u52AA\u529B\uFF0C\u5185\u5BB9\u4E0D\u4E00\u5B9A\u3002",
    reflectionQuestion: "\u5173\u5C0F\u58F0\u8FD8\u6210\u7ACB\u5417\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-038",
    title: "\u622A\u56FE\u4E4B\u5916",
    shortAnswer: "\u622A\u56FE\u5F88\u65B9\uFF0C\u4E16\u754C\u4E0D\u662F\u3002",
    reflectionQuestion: "\u8FB9\u6846\u5916\u85CF\u4E86\u4EC0\u4E48\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-039",
    title: "\u4E09\u4E2A\u6545\u4E8B",
    shortAnswer: "\u4E09\u6B21\u5DE7\u5408\uFF0C\u5DF2\u7ECF\u4F1A\u81EA\u5DF1\u8D77\u6807\u9898\u4E86\u3002",
    reflectionQuestion: "\u6807\u9898\u53EF\u4FE1\u5417\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-040",
    title: "\u4E00\u8D77\u51FA\u73B0",
    shortAnswer: "\u96E8\u4F1E\u548C\u4E0B\u96E8\u603B\u4E00\u8D77\uFF0C\u4F1E\u6CA1\u4E0B\u96E8\u3002",
    reflectionQuestion: "\u8C01\u624D\u662F\u539F\u56E0\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-041",
    title: "\u670B\u53CB\u7684\u670B\u53CB",
    shortAnswer: "\u8D70\u4E86\u4E09\u624B\u7684\u8BDD\uFF0C\u5BB9\u6613\u957F\u51FA\u5C3E\u5DF4\u3002",
    reflectionQuestion: "\u539F\u8BDD\u8FD8\u8BA4\u5F97\u5417\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-042",
    title: "\u6570\u5B57\u7A7F\u642D",
    shortAnswer: "\u6570\u5B57\u6362\u4E2A\u5206\u6BCD\uFF0C\u6C14\u8D28\u5C31\u53D8\u4E86\u3002",
    reflectionQuestion: "\u5B83\u4ECA\u5929\u7A7F\u7684\u54EA\u5957\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-043",
    title: "\u5E78\u5B58\u53D1\u8A00",
    shortAnswer: "\u7559\u4E0B\u7684\u4EBA\uFF0C\u90FD\u5F88\u64C5\u957F\u7559\u4E0B\u3002",
    reflectionQuestion: "\u6CA1\u7559\u4E0B\u7684\u5462\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-044",
    title: "\u65E7\u95FB\u7FFB\u65B0",
    shortAnswer: "\u6628\u5929\u7684\u9762\u5305\uFF0C\u4ECA\u5929\u6362\u4E86\u5305\u88C5\u3002",
    reflectionQuestion: "\u65E5\u671F\u85CF\u54EA\u513F\u4E86\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-045",
    title: "\u5355\u4EBA\u5408\u5531",
    shortAnswer: "\u5341\u4E2A\u8F6C\u53D1\uFF0C\u4E5F\u53EF\u80FD\u53EA\u6709\u4E00\u4E2A\u4EBA\u5728\u5531\u3002",
    reflectionQuestion: "\u771F\u6709\u5341\u4E2A\u4EBA\u5417\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-046",
    title: "\u6807\u70B9\u5F88\u5FD9",
    shortAnswer: "\u4E09\u4E2A\u611F\u53F9\u53F7\uFF0C\u9876\u4E0D\u4E0A\u4E00\u4E2A\u51FA\u5904\u3002",
    reflectionQuestion: "\u51FA\u5904\u5728\u5417\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-047",
    title: "\u770B\u8D77\u6765\u50CF",
    shortAnswer: "\u957F\u5F97\u50CF\u7B54\u6848\uFF0C\u662F\u7B54\u6848\u7684\u5E38\u7528\u4F2A\u88C5\u3002",
    reflectionQuestion: "\u6458\u6389\u6EE4\u955C\u5462\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-048",
    title: "\u518D\u95EE\u4E00\u53E5",
    shortAnswer: "\u8BA4\u771F\u8FFD\u95EE\uFF0C\u662F\u4F20\u8A00\u7684\u6563\u573A\u94C3\u3002",
    reflectionQuestion: "\u5B83\u4F1A\u7559\u4E0B\u5417\uFF1F",
    boundary: "\u53EA\u662F\u4E00\u79CD\u8BF4\u6CD5\uFF0C\u4E0D\u66FF\u4EE3\u4F60\u7684\u72EC\u7ACB\u5224\u65AD\u3002",
    category: "evidence",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-049",
    title: "\u96E8\u4F1E\u95EE\u9898",
    shortAnswer: "\u6674\u5929\u5E26\u4F1E\u6709\u70B9\u50BB\uFF0C\u6DCB\u96E8\u66F4\u50BB\u3002",
    reflectionQuestion: "\u4F60\u6015\u54EA\u79CD\u50BB\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-050",
    title: "\u53E3\u888B\u6DF1\u6D45",
    shortAnswer: "\u5634\u4E0A\u8BF4\u6CA1\u4E8B\uFF0C\u53E3\u888B\u53EF\u80FD\u6709\u610F\u89C1\u3002",
    reflectionQuestion: "\u5B83\u540C\u610F\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-051",
    title: "\u5907\u7528\u94A5\u5319",
    shortAnswer: "\u5907\u7528\u94A5\u5319\u5E73\u65F6\u6700\u50CF\u5E9F\u7269\u3002",
    reflectionQuestion: "\u771F\u7528\u65F6\u627E\u5F97\u5230\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-052",
    title: "\u9E21\u86CB\u5F00\u4F1A",
    shortAnswer: "\u7BEE\u5B50\u5F88\u591A\uFF0C\u684C\u5B50\u53EF\u80FD\u53EA\u6709\u4E00\u5F20\u3002",
    reflectionQuestion: "\u684C\u5B50\u7A33\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-053",
    title: "\u61C2\u4E86\u5927\u6982",
    shortAnswer: "\u201C\u5927\u6982\u61C2\u4E86\u201D\u91CC\u7684\u5927\u6982\uFF0C\u5F88\u5927\u3002",
    reflectionQuestion: "\u5230\u5E95\u591A\u5927\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-054",
    title: "\u5F39\u7C27\u5E8A\u57AB",
    shortAnswer: "\u653E\u5927\u7684\u4E0D\u53EA\u5FEB\u4E50\uFF0C\u8FD8\u6709\u534A\u591C\u3002",
    reflectionQuestion: "\u7761\u5F97\u7740\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-055",
    title: "\u9000\u8DEF\u98CE\u666F",
    shortAnswer: "\u9000\u8DEF\u4E0D\u6D6A\u6F2B\uFF0C\u4F46\u901A\u5E38\u6709\u8DEF\u706F\u3002",
    reflectionQuestion: "\u706F\u4EAE\u7740\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-056",
    title: "\u884C\u674E\u989D\u5EA6",
    shortAnswer: "\u80FD\u62CE\u52A8\uFF0C\u548C\u60F3\u62CE\u4E00\u8DEF\uFF0C\u662F\u4E24\u56DE\u4E8B\u3002",
    reflectionQuestion: "\u8981\u8D70\u591A\u8FDC\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-057",
    title: "\u5C0F\u6982\u7387\u5148\u751F",
    shortAnswer: "\u4ED6\u4E0D\u5E38\u6765\uFF0C\u6240\u4EE5\u6BCF\u6B21\u90FD\u4E0D\u6253\u62DB\u547C\u3002",
    reflectionQuestion: "\u95E8\u9501\u597D\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-058",
    title: "\u540C\u4E00\u628A\u4F1E",
    shortAnswer: "\u770B\u7740\u7AD9\u5F97\u5F88\u6563\uFF0C\u5176\u5B9E\u5171\u7528\u4E00\u628A\u4F1E\u3002",
    reflectionQuestion: "\u96E8\u5927\u4E86\u5462\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-059",
    title: "\u8BF4\u660E\u4E66",
    shortAnswer: "\u770B\u4E0D\u61C2\u7684\u6309\u94AE\uFF0C\u6309\u4E0B\u53BB\u4E5F\u4F1A\u4EAE\u3002",
    reflectionQuestion: "\u4EAE\u4E86\u5C31\u61C2\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-060",
    title: "\u7559\u5F20\u6905\u5B50",
    shortAnswer: "\u610F\u5916\u6765\u8BBF\u65F6\uFF0C\u6700\u597D\u8FD8\u6709\u6905\u5B50\u3002",
    reflectionQuestion: "\u5BB6\u91CC\u5750\u6EE1\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u64CD\u4F5C\u6307\u4EE4\uFF0C\u53EA\u966A\u4F60\u591A\u60F3\u534A\u79D2\u3002",
    category: "risk",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-061",
    title: "\u5FC3\u91CC\u6709\u620F",
    shortAnswer: "\u6F14\u5458\u5F88\u591A\uFF0C\u5BFC\u6F14\u4E34\u65F6\u8BF7\u5047\u4E86\u3002",
    reflectionQuestion: "\u8C01\u5728\u62A2\u53F0\u8BCD\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-062",
    title: "\u4E0D\u670D\u4E00\u4E0B",
    shortAnswer: "\u201C\u6211\u4E0D\u670D\u201D\u5F88\u54CD\uFF0C\u201C\u4E3A\u4EC0\u4E48\u201D\u5F88\u5C0F\u3002",
    reflectionQuestion: "\u5C0F\u58F0\u90A3\u53E5\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-063",
    title: "\u522B\u4EBA\u5BB6\u7684",
    shortAnswer: "\u522B\u4EBA\u5BB6\u7684\u8FDB\u5EA6\u6761\uFF0C\u4E0D\u88C5\u5728\u4F60\u624B\u673A\u91CC\u3002",
    reflectionQuestion: "\u76EF\u5B83\u5E72\u4EC0\u4E48\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-064",
    title: "\u540E\u6094\u9884\u544A",
    shortAnswer: "\u4E8B\u60C5\u6CA1\u53D1\u751F\uFF0C\u540E\u6094\u5148\u6765\u5360\u5EA7\u3002",
    reflectionQuestion: "\u7968\u662F\u8C01\u4E70\u7684\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-065",
    title: "\u8FD0\u6C14\u9886\u529F",
    shortAnswer: "\u8FD0\u6C14\u7A7F\u4E0A\u897F\u88C5\uFF0C\u5C31\u50CF\u5B9E\u529B\u672C\u4EBA\u3002",
    reflectionQuestion: "\u9886\u5E26\u8C01\u7CFB\u7684\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-066",
    title: "\u6015\u6765\u4E0D\u53CA",
    shortAnswer: "\u8D8A\u6015\u6765\u4E0D\u53CA\uFF0C\u65F6\u95F4\u8D8A\u7231\u770B\u70ED\u95F9\u3002",
    reflectionQuestion: "\u5B83\u771F\u7684\u8981\u5173\u95E8\u5417\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-067",
    title: "\u8111\u5B50\u6CA1\u7535",
    shortAnswer: "\u767E\u5206\u4E4B\u4E00\u7684\u7535\uFF0C\u4E5F\u6562\u5F00\u5341\u4E2A\u5E94\u7528\u3002",
    reflectionQuestion: "\u5148\u5145\u4F1A\u513F\u5417\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-068",
    title: "\u7FA4\u804A\u6CB8\u817E",
    shortAnswer: "\u4E00\u767E\u6761\u6D88\u606F\uFF0C\u53EF\u80FD\u53EA\u716E\u5F00\u4E86\u4E00\u58F6\u6C34\u3002",
    reflectionQuestion: "\u6C34\u91CC\u6709\u4EC0\u4E48\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-069",
    title: "\u8F93\u8D62\u8D34\u7EB8",
    shortAnswer: "\u8D34\u7EB8\u8D34\u5728\u8EAB\u4E0A\uFF0C\u6495\u4E0B\u6765\u4E5F\u8FD8\u662F\u4F60\u3002",
    reflectionQuestion: "\u975E\u8D34\u4E0D\u53EF\u5417\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-070",
    title: "\u5750\u7ACB\u4E0D\u5B89",
    shortAnswer: "\u6905\u5B50\u6CA1\u6709\u9519\uFF0C\u4ECA\u5929\u5148\u522B\u602A\u5B83\u3002",
    reflectionQuestion: "\u662F\u8C01\u5750\u4E0D\u4F4F\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-071",
    title: "\u6DF1\u547C\u5438\u6D3E",
    shortAnswer: "\u7A7A\u6C14\u514D\u8D39\uFF0C\u4F46\u7ECF\u5E38\u88AB\u5FD8\u8BB0\u4F7F\u7528\u3002",
    reflectionQuestion: "\u8981\u4E0D\u8981\u9886\u4E00\u4EFD\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-072",
    title: "\u60C5\u7EEA\u5929\u6C14",
    shortAnswer: "\u5FC3\u91CC\u4E0B\u96E8\uFF0C\u4E0D\u4EE3\u8868\u7A97\u5916\u4E5F\u4E0B\u3002",
    reflectionQuestion: "\u7A97\u5E18\u62C9\u5F00\u4E86\u5417\uFF1F",
    boundary: "\u53EA\u804A\u5F53\u4E0B\u611F\u53D7\uFF0C\u4E0D\u8BC4\u4EF7\u5177\u4F53\u64CD\u4F5C\u3002",
    category: "emotion",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-073",
    title: "\u94C5\u7B14\u8BB0\u5F97",
    shortAnswer: "\u8111\u5B50\u4F1A\u6539\u7A3F\uFF0C\u94C5\u7B14\u6BD4\u8F83\u56FA\u6267\u3002",
    reflectionQuestion: "\u5F53\u65F6\u5199\u4E86\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-074",
    title: "\u4F8B\u5916\u5148\u751F",
    shortAnswer: "\u4ED6\u6BCF\u5468\u53EA\u6765\u4E00\u6B21\uFF0C\u5DF2\u7ECF\u6765\u4E86\u4E03\u5929\u3002",
    reflectionQuestion: "\u4ECA\u5929\u53C8\u662F\u4ED6\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-075",
    title: "\u4E00\u53E5\u5C31\u591F",
    shortAnswer: "\u7406\u7531\u6392\u6210\u961F\uFF0C\u53EF\u80FD\u53EA\u662F\u6765\u58EE\u80C6\u3002",
    reflectionQuestion: "\u961F\u957F\u662F\u8C01\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-076",
    title: "\u7B49\u53F7\u5F88\u5FD9",
    shortAnswer: "\u60F3\u5230\u4E86\uFF0C\u4E0D\u7B49\u4E8E\u60F3\u597D\u4E86\u3002",
    reflectionQuestion: "\u4E2D\u95F4\u5C11\u4E86\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-077",
    title: "\u65E7\u4FBF\u7B7E",
    shortAnswer: "\u4E8B\u524D\u7684\u5B57\u4E11\uFF0C\u4F46\u901A\u5E38\u6BD4\u8F83\u8BDA\u5B9E\u3002",
    reflectionQuestion: "\u8FD8\u770B\u5F97\u6E05\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-078",
    title: "\u4E34\u65F6\u51B3\u5B9A",
    shortAnswer: "\u201C\u4E34\u65F6\u201D\u4F4F\u4E45\u4E86\uFF0C\u4E5F\u4F1A\u6536\u5FEB\u9012\u3002",
    reflectionQuestion: "\u5B83\u4F4F\u591A\u4E45\u4E86\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-079",
    title: "\u6309\u94AE\u5F88\u4EAE",
    shortAnswer: "\u6309\u94AE\u4EAE\u7740\uFF0C\u53EA\u8BF4\u660E\u5B83\u901A\u7535\u3002",
    reflectionQuestion: "\u4F60\u4E5F\u901A\u7535\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-080",
    title: "\u518D\u6765\u4E00\u6B21",
    shortAnswer: "\u540C\u6837\u7684\u95E8\uFF0C\u649E\u7B2C\u4E8C\u6B21\u58F0\u97F3\u66F4\u719F\u3002",
    reflectionQuestion: "\u95E8\u53D8\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-081",
    title: "\u7406\u7531\u52A0\u957F",
    shortAnswer: "\u89E3\u91CA\u8D8A\u957F\uFF0C\u53E5\u53F7\u8D8A\u60F3\u9003\u8DD1\u3002",
    reflectionQuestion: "\u80FD\u8BF4\u77ED\u70B9\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-082",
    title: "\u660E\u65E5\u7248\u672C",
    shortAnswer: "\u660E\u5929\u7684\u4F60\uFF0C\u53EF\u80FD\u4E0D\u8BA4\u4ECA\u5929\u7684\u8865\u4E01\u3002",
    reflectionQuestion: "\u8981\u66F4\u65B0\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-083",
    title: "\u5148\u653E\u684C\u4E0A",
    shortAnswer: "\u653E\u4E00\u4F1A\u513F\uFF0C\u51B2\u52A8\u4F1A\u81EA\u5DF1\u663E\u539F\u5F62\u3002",
    reflectionQuestion: "\u5B83\u957F\u4EC0\u4E48\u6837\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-084",
    title: "\u624B\u5199\u5C0F\u5B57",
    shortAnswer: "\u5C0F\u5B57\u4E0D\u662F\u91CD\u70B9\uFF0C\u5374\u5E38\u5E38\u6700\u8BDA\u5B9E\u3002",
    reflectionQuestion: "\u4F60\u8DF3\u8FC7\u54EA\u884C\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u4EA4\u6613\u6B65\u9AA4\uFF0C\u8FD9\u9875\u53EA\u8D1F\u8D23\u7728\u773C\u3002",
    category: "discipline",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-085",
    title: "\u6807\u9898\u5148\u8DD1",
    shortAnswer: "\u6B63\u6587\u8FD8\u5728\u7CFB\u978B\u5E26\uFF0C\u6807\u9898\u5DF2\u7ECF\u51B2\u7EBF\u3002",
    reflectionQuestion: "\u7B49\u6B63\u6587\u5417\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-086",
    title: "\u636E\u8BF4\u672C\u4EBA",
    shortAnswer: "\u201C\u636E\u8BF4\u201D\u4ECE\u4E0D\u7559\u4E0B\u8054\u7CFB\u65B9\u5F0F\u3002",
    reflectionQuestion: "\u8FD9\u6B21\u7559\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-087",
    title: "\u8F6C\u53D1\u5341\u6B21",
    shortAnswer: "\u8BDD\u8D70\u5F97\u8D8A\u8FDC\uFF0C\u884C\u674E\u8D8A\u591A\u3002",
    reflectionQuestion: "\u591A\u4E86\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-088",
    title: "\u6628\u5929\u4ECA\u5929",
    shortAnswer: "\u65E7\u6D88\u606F\u6362\u4EF6\u65B0\u5916\u5957\uFF0C\u4E5F\u633A\u7CBE\u795E\u3002",
    reflectionQuestion: "\u540A\u724C\u8FD8\u5728\u5417\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-089",
    title: "\u533F\u540D\u4EB2\u621A",
    shortAnswer: "\u670B\u53CB\u7684\u8868\u54E5\uFF0C\u4E1A\u52A1\u8303\u56F4\u5F88\u5E7F\u3002",
    reflectionQuestion: "\u4ED6\u4ECA\u5929\u53C8\u61C2\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-090",
    title: "\u53EA\u622A\u4E00\u534A",
    shortAnswer: "\u53E6\u4E00\u534A\u53EF\u80FD\u6B63\u5728\u7533\u8BF7\u51FA\u955C\u3002",
    reflectionQuestion: "\u8BA9\u5B83\u8FDB\u6765\u5417\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-091",
    title: "\u611F\u53F9\u53F7\u4EEC",
    shortAnswer: "\u5B83\u4EEC\u6392\u5F97\u5F88\u9F50\uFF0C\u5C31\u662F\u6CA1\u5E26\u6765\u6E90\u3002",
    reflectionQuestion: "\u6765\u6E90\u8FDF\u5230\u4E86\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-092",
    title: "\u70ED\u641C\u4F53\u6E29",
    shortAnswer: "\u5F88\u70ED\uFF0C\u53EF\u80FD\u53EA\u662F\u4EBA\u591A\u3002",
    reflectionQuestion: "\u5185\u5BB9\u719F\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-093",
    title: "\u6570\u5B57\u72EC\u767D",
    shortAnswer: "\u5206\u6BCD\u4E0D\u5728\uFF0C\u6570\u5B57\u5C31\u5F00\u59CB\u81EA\u7531\u53D1\u6325\u3002",
    reflectionQuestion: "\u642D\u6863\u53BB\u54EA\u513F\u4E86\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-094",
    title: "\u4E13\u5BB6\u5F88\u591A",
    shortAnswer: "\u9EA6\u514B\u98CE\u6570\u91CF\uFF0C\u548C\u7B54\u6848\u6570\u91CF\u4E0D\u662F\u4E00\u56DE\u4E8B\u3002",
    reflectionQuestion: "\u8C01\u6CA1\u62FF\u9EA6\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-095",
    title: "\u521A\u521A\u786E\u8BA4",
    shortAnswer: "\u201C\u521A\u521A\u201D\u5F88\u65B0\uFF0C\u201C\u786E\u8BA4\u201D\u8981\u53E6\u8BF4\u3002",
    reflectionQuestion: "\u8C01\u786E\u8BA4\u7684\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-096",
    title: "\u5237\u65B0\u4E00\u4E0B",
    shortAnswer: "\u5237\u65B0\u5E26\u6765\u65B0\u9875\u9762\uFF0C\u4E0D\u4FDD\u8BC1\u65B0\u4E16\u754C\u3002",
    reflectionQuestion: "\u624B\u6307\u7D2F\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u8BA4\u53EF\u4E5F\u4E0D\u5426\u5B9A\u4F20\u95FB\uFF0C\u53EA\u63D0\u9192\u5B83\u4F1A\u5316\u5986\u3002",
    category: "information",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-097",
    title: "\u684C\u9762\u592A\u6EE1",
    shortAnswer: "\u676F\u5B50\u5F88\u591A\uFF0C\u80FD\u559D\u6C34\u7684\u5634\u53EA\u6709\u4E00\u4E2A\u3002",
    reflectionQuestion: "\u90FD\u8981\u6446\u7740\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-098",
    title: "\u6362\u4E86\u540D\u5B57",
    shortAnswer: "\u540D\u5B57\u4E0D\u540C\uFF0C\u4E5F\u53EF\u80FD\u7A7F\u540C\u4E00\u53CC\u978B\u3002",
    reflectionQuestion: "\u811A\u5370\u4E00\u6837\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-099",
    title: "\u8D2D\u7269\u888B\u4EEC",
    shortAnswer: "\u888B\u5B50\u5206\u4E86\u4E94\u4E2A\uFF0C\u4E1C\u897F\u6765\u81EA\u4E00\u5BB6\u5E97\u3002",
    reflectionQuestion: "\u771F\u5206\u5F00\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-100",
    title: "\u62FC\u76D8\u827A\u672F",
    shortAnswer: "\u989C\u8272\u5F88\u591A\uFF0C\u4E0D\u4EE3\u8868\u5473\u9053\u5F88\u591A\u3002",
    reflectionQuestion: "\u5C1D\u8D77\u6765\u5462\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-101",
    title: "\u51B0\u7BB1\u6DF1\u5904",
    shortAnswer: "\u653E\u5F97\u4E45\uFF0C\u4E0D\u7B49\u4E8E\u8FD8\u8BB0\u5F97\u4E3A\u4EC0\u4E48\u4E70\u3002",
    reflectionQuestion: "\u90A3\u76D2\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-102",
    title: "\u5DE5\u5177\u7BB1",
    shortAnswer: "\u6273\u624B\u5F88\u591A\uFF0C\u624B\u8FD8\u662F\u4E24\u53EA\u3002",
    reflectionQuestion: "\u7528\u5F97\u8FC7\u6765\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-103",
    title: "\u884C\u674E\u6253\u5305",
    shortAnswer: "\u6BCF\u4EF6\u90FD\u91CD\u8981\uFF0C\u7BB1\u5B50\u5C31\u5173\u4E0D\u4E0A\u3002",
    reflectionQuestion: "\u8C01\u5750\u7BB1\u5B50\u4E0A\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-104",
    title: "\u540C\u6B3E\u96E8\u8863",
    shortAnswer: "\u770B\u7740\u4E94\u989C\u516D\u8272\uFF0C\u96E8\u6765\u4E86\u90FD\u6E7F\u3002",
    reflectionQuestion: "\u5DEE\u522B\u5728\u54EA\u513F\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-105",
    title: "\u6807\u7B7E\u6389\u4E86",
    shortAnswer: "\u6807\u7B7E\u4E00\u6389\uFF0C\u6709\u4E9B\u4E1C\u897F\u7A81\u7136\u5F88\u964C\u751F\u3002",
    reflectionQuestion: "\u8FD8\u8BA4\u5F97\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-106",
    title: "\u623F\u95F4\u7528\u9014",
    shortAnswer: "\u5BB6\u5177\u632A\u591A\u4E86\uFF0C\u53EF\u80FD\u5FD8\u4E86\u8FD9\u662F\u5367\u5BA4\u3002",
    reflectionQuestion: "\u539F\u6765\u8981\u505A\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-107",
    title: "\u5907\u7528\u62BD\u5C49",
    shortAnswer: "\u7A7A\u62BD\u5C49\u770B\u7740\u6D6A\u8D39\uFF0C\u627E\u4E1C\u897F\u65F6\u5F88\u9999\u3002",
    reflectionQuestion: "\u7559\u4E00\u4E2A\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-108",
    title: "\u7B80\u5355\u4E00\u70B9",
    shortAnswer: "\u80FD\u4E00\u53E3\u8BF4\u5B8C\uFF0C\u901A\u5E38\u6BD4\u8F83\u597D\u8BB0\u3002",
    reflectionQuestion: "\u4E00\u53E3\u591F\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u6BD4\u4F8B\u6216\u4EA7\u54C1\u5EFA\u8BAE\uFF0C\u53EA\u770B\u770B\u684C\u9762\u3002",
    category: "portfolio",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-109",
    title: "\u5F55\u50CF\u91CD\u64AD",
    shortAnswer: "\u8BB0\u5FC6\u526A\u6389\u7684\uFF0C\u5F80\u5F80\u6B63\u597D\u662F\u91CD\u70B9\u3002",
    reflectionQuestion: "\u54EA\u6BB5\u4E0D\u89C1\u4E86\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-110",
    title: "\u4E8B\u540E\u7F16\u5267",
    shortAnswer: "\u7ED3\u5C40\u4E00\u51FA\uFF0C\u4F0F\u7B14\u7A81\u7136\u5230\u5904\u90FD\u662F\u3002",
    reflectionQuestion: "\u5F53\u65F6\u771F\u770B\u89C1\u4E86\u5417\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-111",
    title: "\u53C8\u89C1\u9762\u4E86",
    shortAnswer: "\u540C\u4E00\u4E2A\u5751\uFF0C\u4ECA\u5929\u6362\u4E86\u9876\u5E3D\u5B50\u3002",
    reflectionQuestion: "\u8BA4\u51FA\u6765\u4E86\u5417\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-112",
    title: "\u6539\u4E00\u4E2A\u5B57",
    shortAnswer: "\u6574\u7BC7\u91CD\u5199\u5F88\u7D2F\uFF0C\u5148\u6539\u4E00\u4E2A\u5B57\u3002",
    reflectionQuestion: "\u6539\u54EA\u4E2A\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-113",
    title: "\u8FD0\u6C14\u5165\u955C",
    shortAnswer: "\u5B83\u7AD9\u5728\u89D2\u843D\uFF0C\u5374\u603B\u88AB\u88C1\u6389\u3002",
    reflectionQuestion: "\u8FD9\u6B21\u62CD\u5230\u6CA1\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-114",
    title: "\u638C\u58F0\u592A\u65E9",
    shortAnswer: "\u7247\u5C3E\u8FD8\u6CA1\u653E\u5B8C\uFF0C\u5148\u522B\u6025\u7740\u8C22\u5E55\u3002",
    reflectionQuestion: "\u5F69\u86CB\u5462\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-115",
    title: "\u501F\u53E3\u5230\u8D27",
    shortAnswer: "\u4E0B\u5355\u65F6\u6CA1\u6709\uFF0C\u590D\u76D8\u65F6\u5305\u90AE\u9001\u8FBE\u3002",
    reflectionQuestion: "\u8981\u7B7E\u6536\u5417\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-116",
    title: "\u65E7\u95EE\u9898",
    shortAnswer: "\u7B54\u6848\u6362\u4E86\uFF0C\u95EE\u9898\u53EF\u80FD\u6CA1\u6362\u3002",
    reflectionQuestion: "\u8FD8\u662F\u90A3\u4E00\u4E2A\u5417\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-117",
    title: "\u7EA2\u7B14\u84DD\u7B14",
    shortAnswer: "\u7EA2\u7B14\u5708\u9519\uFF0C\u84DD\u7B14\u4E5F\u8BE5\u5708\u5DE7\u5408\u3002",
    reflectionQuestion: "\u84DD\u7B14\u5728\u54EA\u513F\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-118",
    title: "\u4E00\u9875\u8DB3\u591F",
    shortAnswer: "\u5199\u592A\u591A\uFF0C\u771F\u8BDD\u4F1A\u8EB2\u8FDB\u9644\u5F55\u3002",
    reflectionQuestion: "\u54EA\u53E5\u6700\u77ED\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-119",
    title: "\u4E0B\u6B21\u7684\u4F60",
    shortAnswer: "\u4ED6\u4E0D\u9700\u8981\u6F14\u8BB2\uFF0C\u53EA\u8981\u4E00\u5F20\u4FBF\u7B7E\u3002",
    reflectionQuestion: "\u5199\u54EA\u4E00\u53E5\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-120",
    title: "\u955C\u5B50\u8D77\u96FE",
    shortAnswer: "\u64E6\u4E00\u5C0F\u5757\uFF0C\u4E5F\u6BD4\u60F3\u8C61\u5168\u8138\u5F3A\u3002",
    reflectionQuestion: "\u5148\u64E6\u54EA\u91CC\uFF1F",
    boundary: "\u53EA\u662F\u56DE\u5934\u770B\u4E00\u773C\uFF0C\u4E0D\u751F\u6210\u5F52\u56E0\u7ED3\u8BBA\u3002",
    category: "review",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-121",
    title: "\u672A\u6765\u6CA1\u56DE\u4FE1",
    shortAnswer: "\u53EF\u80FD\u5728\u8DEF\u4E0A\uFF0C\u4E5F\u53EF\u80FD\u6CA1\u8D34\u90AE\u7968\u3002",
    reflectionQuestion: "\u8FD8\u8981\u50AC\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-122",
    title: "\u5927\u6982\u5148\u751F",
    shortAnswer: "\u4ED6\u8BF4\u5F97\u5F88\u6EE1\uFF0C\u540D\u5B57\u5374\u53EB\u5927\u6982\u3002",
    reflectionQuestion: "\u4FE1\u54EA\u4E2A\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-123",
    title: "\u7CBE\u51C6\u5230\u70B9",
    shortAnswer: "\u5C0F\u6570\u70B9\u5F88\u8BA4\u771F\uFF0C\u4E16\u754C\u6BD4\u8F83\u968F\u610F\u3002",
    reflectionQuestion: "\u8C01\u4F1A\u5148\u6539\u53E3\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-124",
    title: "\u8FD8\u6709\u4E00\u79CD",
    shortAnswer: "\u4F60\u5217\u4E86\u4E09\u79CD\uFF0C\u73B0\u5B9E\u559C\u6B22\u7B2C\u56DB\u79CD\u3002",
    reflectionQuestion: "\u6905\u5B50\u591F\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-125",
    title: "\u660E\u5929\u813E\u6C14",
    shortAnswer: "\u660E\u5929\u8FD8\u6CA1\u8D77\u5E8A\uFF0C\u5148\u522B\u66FF\u5B83\u8BF4\u8BDD\u3002",
    reflectionQuestion: "\u8BA9\u5B83\u81EA\u5DF1\u8BF4\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-126",
    title: "\u5730\u56FE\u8FB9\u7F18",
    shortAnswer: "\u753B\u5B8C\u7684\u5730\u65B9\uFF0C\u4E0D\u7B49\u4E8E\u4E16\u754C\u5C3D\u5934\u3002",
    reflectionQuestion: "\u5916\u9762\u662F\u4EC0\u4E48\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-127",
    title: "\u719F\u6089\u9519\u89C9",
    shortAnswer: "\u89C1\u8FC7\u5F88\u591A\u6B21\uFF0C\u4E5F\u53EF\u80FD\u53EA\u662F\u8138\u719F\u3002",
    reflectionQuestion: "\u771F\u7684\u8BA4\u8BC6\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-128",
    title: "\u8BEF\u5DEE\u672C\u4EBA",
    shortAnswer: "\u5B83\u4E0D\u5728\u5907\u6CE8\u91CC\uFF0C\u4E5F\u4F1A\u51C6\u65F6\u51FA\u5E2D\u3002",
    reflectionQuestion: "\u7ED9\u5B83\u7559\u5EA7\u4E86\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-129",
    title: "\u5148\u4E0D\u56DE\u7B54",
    shortAnswer: "\u7A7A\u767D\u4E0D\u662F\u5931\u8D25\uFF0C\u662F\u7EB8\u8FD8\u5728\u547C\u5438\u3002",
    reflectionQuestion: "\u6025\u7740\u5199\u6EE1\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-130",
    title: "\u610F\u5916\u5609\u5BBE",
    shortAnswer: "\u6CA1\u5728\u540D\u5355\u4E0A\uFF0C\u7167\u6837\u80FD\u4E0A\u53F0\u3002",
    reflectionQuestion: "\u5907\u7528\u9EA6\u5728\u54EA\u513F\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-131",
    title: "\u65F6\u95F4\u6EE4\u955C",
    shortAnswer: "\u770B\u5F97\u8FDC\uFF0C\u4E0D\u4EE3\u8868\u770B\u5F97\u6E05\u3002",
    reflectionQuestion: "\u96FE\u6709\u591A\u5927\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-132",
    title: "\u4E0D\u77E5\u9053",
    shortAnswer: "\u8FD9\u4E09\u4E2A\u5B57\uFF0C\u6709\u65F6\u6BD4\u957F\u53E5\u66F4\u5B8C\u6574\u3002",
    reflectionQuestion: "\u6562\u8BA9\u5B83\u5355\u72EC\u4E00\u884C\u5417\uFF1F",
    boundary: "\u4E0D\u63D0\u4F9B\u65B9\u5411\u5224\u65AD\uFF0C\u672A\u6765\u4E5F\u6CA1\u6765\u6295\u7A3F\u3002",
    category: "uncertainty",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-133",
    title: "\u996D\u8FD8\u70ED\u5417",
    shortAnswer: "\u6570\u5B57\u4E0D\u4F1A\u51C9\uFF0C\u996D\u4F1A\u3002",
    reflectionQuestion: "\u5148\u987E\u54EA\u8FB9\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-134",
    title: "\u6795\u5934\u6297\u8BAE",
    shortAnswer: "\u5B83\u7B49\u4F60\u5F88\u4E45\uFF0C\u5DF2\u7ECF\u4E0D\u60F3\u5F00\u4F1A\u3002",
    reflectionQuestion: "\u4ECA\u665A\u51E0\u70B9\u6563\u4F1A\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-135",
    title: "\u5BB6\u91CC\u6709\u706F",
    shortAnswer: "\u5C4F\u5E55\u518D\u4EAE\uFF0C\u4E5F\u7167\u4E0D\u5230\u9910\u684C\u90A3\u8FB9\u3002",
    reflectionQuestion: "\u8C01\u5728\u7B49\u4F60\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-136",
    title: "\u751F\u6D3B\u8D39\u672C\u4EBA",
    shortAnswer: "\u5B83\u6765\u8D1F\u8D23\u751F\u6D3B\uFF0C\u4E0D\u6765\u53C2\u52A0\u5192\u9669\u3002",
    reflectionQuestion: "\u540D\u5B57\u5199\u6E05\u4E86\u5417\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-137",
    title: "\u6563\u6B65\u8DEF\u7EBF",
    shortAnswer: "\u6709\u4E9B\u7B54\u6848\uFF0C\u8D70\u4E24\u6761\u8857\u5C31\u53D8\u5C0F\u4E86\u3002",
    reflectionQuestion: "\u978B\u5728\u54EA\u513F\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-138",
    title: "\u5173\u673A\u4E94\u5206\u949F",
    shortAnswer: "\u4E16\u754C\u5927\u6982\u7387\u4F1A\u81EA\u5DF1\u8F6C\u3002",
    reflectionQuestion: "\u8981\u8BD5\u8BD5\u770B\u5417\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-139",
    title: "\u4F60\u4E0D\u7B49\u4E8E\u5B83",
    shortAnswer: "\u4E00\u4E2A\u6570\u5B57\uFF0C\u88C5\u4E0D\u4E0B\u4E00\u4E2A\u4EBA\u3002",
    reflectionQuestion: "\u8FD8\u8BB0\u5F97\u522B\u7684\u81EA\u5DF1\u5417\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-140",
    title: "\u5148\u7761\u4E00\u89C9",
    shortAnswer: "\u68A6\u4E0D\u8D1F\u8D23\u89E3\u7B54\uFF0C\u4F46\u8D1F\u8D23\u5173\u706F\u3002",
    reflectionQuestion: "\u4ECA\u665A\u8BA9\u5B83\u503C\u73ED\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-141",
    title: "\u627E\u4E2A\u4EBA\u8BF4",
    shortAnswer: "\u8BF4\u51FA\u53E3\u4EE5\u540E\uFF0C\u602A\u517D\u901A\u5E38\u4F1A\u7F29\u6C34\u3002",
    reflectionQuestion: "\u627E\u8C01\u5408\u9002\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-142",
    title: "\u5468\u672B\u540D\u5355",
    shortAnswer: "\u540D\u5355\u91CC\u5982\u679C\u6CA1\u6709\u751F\u6D3B\uFF0C\u5C31\u6709\u70B9\u53EF\u7591\u3002",
    reflectionQuestion: "\u6F0F\u4E86\u4EC0\u4E48\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-143",
    title: "\u624B\u673A\u671D\u4E0B",
    shortAnswer: "\u684C\u9762\u7A81\u7136\u591A\u51FA\u4E00\u6574\u7247\u5929\u7A7A\u3002",
    reflectionQuestion: "\u770B\u89C1\u4E86\u5417\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
    reviewStatus: "approved"
  },
  {
    id: "card-144",
    title: "\u56DE\u5230\u6B64\u523B",
    shortAnswer: "\u672A\u6765\u5F88\u5FD9\uFF0C\u6B64\u523B\u6B63\u5728\u95E8\u53E3\u7B49\u4F60\u3002",
    reflectionQuestion: "\u8981\u5F00\u95E8\u5417\uFF1F",
    boundary: "\u751F\u6D3B\u4F18\u5148\uFF1B\u590D\u6742\u95EE\u9898\u8BF7\u54A8\u8BE2\u6709\u8D44\u8D28\u7684\u4E13\u4E1A\u4EBA\u58EB\u3002",
    category: "life",
    version: "2.0.0",
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

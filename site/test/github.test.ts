// node --experimental-strip-types --test test/github.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { requestRemake, updateFile } from "../src/lib/github.ts";

const env = { GITHUB_REPO: "o/r", GITHUB_BRANCH: "main", GITHUB_TOKEN: "t" } as any;
const append = (cur: string | null) => (cur ?? "").replace(/\n*$/, cur ? "\n" : "") + '{"c":"é"}\n';

test("appends feedback, keeps existing lines, retries when another save lands first", async () => {
  let file: { text: string; sha: string } = { text: '{"a":1}\n', sha: "s1" };
  let puts = 0;
  globalThis.fetch = (async (_url: string, init?: RequestInit) => {
    if (!init?.method) return Response.json({ content: Buffer.from(file.text).toString("base64"), sha: file.sha });
    const body = JSON.parse(String(init.body));
    assert.equal(body.branch, "main");
    puts++;
    if (puts === 1) {
      // Someone else saved in between, so this write is refused and retried on top of theirs.
      file = { text: file.text + '{"b":2}\n', sha: "s2" };
      return new Response("conflict", { status: 409 });
    }
    assert.equal(body.sha, file.sha);
    file = { text: Buffer.from(body.content, "base64").toString(), sha: "s3" };
    return Response.json({});
  }) as any;

  await updateFile(env, "shows/grace/feedback.jsonl", append, "msg");
  assert.equal(file.text, '{"a":1}\n{"b":2}\n{"c":"é"}\n');
  assert.equal(puts, 2);
});

test("creates the file when it does not exist yet", async () => {
  let created: string | null = null;
  globalThis.fetch = (async (_url: string, init?: RequestInit) => {
    if (!init?.method) return new Response("", { status: 404 });
    const body = JSON.parse(String(init.body));
    assert.equal(body.sha, undefined);
    created = Buffer.from(body.content, "base64").toString();
    return Response.json({});
  }) as any;
  await updateFile(env, "shows/grace/feedback.jsonl", append, "msg");
  assert.equal(created, '{"c":"é"}\n');
});

test("gives up with an error after repeated conflicts", async () => {
  globalThis.fetch = (async (_url: string, init?: RequestInit) =>
    init?.method ? new Response("", { status: 409 }) : new Response("", { status: 404 })) as any;
  await assert.rejects(updateFile(env, "x", append, "msg"));
});

test("asks for a remake by pushing a claude/remake-SHOW-TIME branch at main's head", async () => {
  const calls: { url: string; body?: any }[] = [];
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (!init?.method) return Response.json({ object: { sha: "abc123" } });
    return Response.json({}, { status: 201 });
  }) as any;
  await requestRemake({ ...env, SHOW: "grace" });
  assert.equal(calls[0].url, "https://api.github.com/repos/o/r/git/ref/heads/main");
  assert.equal(calls[1].url, "https://api.github.com/repos/o/r/git/refs");
  assert.equal(calls[1].body.sha, "abc123");
  assert.match(calls[1].body.ref, /^refs\/heads\/claude\/remake-grace-\d+$/);
});

test("a refused remake request is an error", async () => {
  globalThis.fetch = (async (_url: string, init?: RequestInit) =>
    init?.method ? new Response("", { status: 403 }) : Response.json({ object: { sha: "abc" } })) as any;
  await assert.rejects(requestRemake({ ...env, SHOW: "grace" }));
});

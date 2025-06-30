import express, { RequestHandler } from 'express';
import vhost from 'vhost';

import { Site } from './site';
import { generate_site_id } from './utils';
import { env } from 'process';
import path from 'path';
import { SYSTEM_PROMPT } from './prompt';

const PORT = 3000;
const DOMAIN = "localhost";

const SITES: Record<number, Site> = {};

const DEFAULT_LLM = "google/gemini-2.0-flash-001";
const OPENROUTER_KEY = env["OPENROUTER_KEY"];

const app     = express();
const llm_app = express();

llm_app.use((req, res, next) => {
   const { method, httpVersion, headers, url } = req;

   let rawBody = '';

   req.on('data', chunk => {
      rawBody += chunk;
   });

   req.on('end', () => {
      const request_line = `${method} ${url} HTTP/${httpVersion}`;
      const raw_headers = Object.entries(headers)
         .map(([key, val]) => `${key}: ${val}`)
         .join('\r\n');

      (req as any).raw = `${request_line}\r\n${raw_headers}\r\n\r\n${rawBody}`;

      next();
   });
});

llm_app.use((async (req, res, next) => {
   const sock = req.socket;

   // Prevent nonsense requests
   if (req.originalUrl?.includes(".well-known") || req.originalUrl?.includes("favicon.ico"))
      return sock.end();

   if (!req.headers.host)
      return sock.end();

   const site_id = +req.headers.host.split(".")[0];

   if (!(site_id in SITES))
      return sock.end();

   console.log(site_id);

   const site = SITES[site_id];

   const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
         Authorization: 'Bearer ' + site.key,
         'Content-Type': 'application/json',
      },
      body: JSON.stringify({
         model: site.llm,
         messages: [
            {
               "role": "system",
               "content": [
                  {
                     "type": "text",
                     "text": SYSTEM_PROMPT + site.prompt,
                  }
               ]
            },
            {
               "role": "user",
               "content": [
                  {
                     "type": "text",
                     "text": (req as any).raw,
                  }
               ]
            }
         ],
      }),
   });

   const llm_http = await response.json();

   sock.write(llm_http.choices[0].message.content);
   sock.end();
}) as RequestHandler);

app.use(vhost(`*.${DOMAIN}`, llm_app));

app.use(express.urlencoded({ extended: true }));

app.get("/", (req, res) => {
   res.sendFile("public/index.html", { root: path.resolve(__dirname, "../") });
});

app.post("/create", (async (req, res) => {
   const { prompt, llm, key } = req.body;

   if (!prompt)
      return res.status(400).json({ error: "Prompt required!" });

   if (llm && !key)
      return res.status(400).json({ error: "Custom LLMs require an OpenRouter API key!" });

   if (key) {
      // Ensure key is valid
      try {
         const response = await fetch(
            'https://openrouter.ai/api/v1/credits', 
            { 
               method: 'GET', 
               headers: { Authorization: 'Bearer ' + key } 
            }
         );

         const data = await response.json();

         if ("error" in data)
            res.status(400).json({ error: "Invalid OpenRouter API key!" });
      } catch (error) {
         return res.status(500).json({ error: "Internal error!" });
      }
   }

   const id = generate_site_id(SITES);

   SITES[id] = {
      id: id,
      prompt: prompt,
      llm: llm || DEFAULT_LLM,
      key: key || OPENROUTER_KEY,
      last_access: new Date()
   };

   console.log(SITES);

   res.redirect(`https://${id}.${DOMAIN}`);
}) as RequestHandler);

app.listen(PORT, () => {
   console.log(`Server is running at http://${DOMAIN}:${PORT}`);
});
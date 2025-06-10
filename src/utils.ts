import { Site } from "./site"

const generate_site_id = (sites: Record<number, Site>) => {
   const id = Math.round(Math.random() * 100000);

   if (id in sites) return generate_site_id(sites);

   return id;
}

export { generate_site_id };
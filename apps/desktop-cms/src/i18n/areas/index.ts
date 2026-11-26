// Every area dictionary of the CMS. Add a new file here when a screen gets its texts.
import type { AreaDict } from "./define";
import { posx } from "./posx";
import { vm } from "./vm";
import { cbf } from "./cbf";
import { cb } from "./cb";
import { pe } from "./pe";
import { errors } from "./errors";
import { field } from "./field";
import { status_label } from "./status_label";
import { app } from "./app";

export const AREAS: AreaDict[] = [app, status_label, field, errors, pe, cb, cbf, vm, posx];

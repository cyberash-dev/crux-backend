import { httpRouter } from "convex/server";
import { readRun, submitRun } from "./clientApi";
import { openExam, readExam, writeExam } from "./examApi";
import { workerRequest } from "./workerApi";

const http = httpRouter();

http.route({ path: "/v1/runs", method: "POST", handler: submitRun });
http.route({ pathPrefix: "/v1/runs/", method: "GET", handler: readRun });
http.route({ pathPrefix: "/v1/runs/", method: "POST", handler: openExam });
http.route({ pathPrefix: "/v1/exams/", method: "GET", handler: readExam });
http.route({ pathPrefix: "/v1/exams/", method: "POST", handler: writeExam });
http.route({ pathPrefix: "/worker/runs/", method: "POST", handler: workerRequest });

export default http;

/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as clientApi from "../clientApi.js";
import type * as config_env from "../config/env.js";
import type * as config_maxParallelRuns from "../config/maxParallelRuns.js";
import type * as config_proxyUrls from "../config/proxyUrls.js";
import type * as crons from "../crons.js";
import type * as dispatcher from "../dispatcher.js";
import type * as examApi from "../examApi.js";
import type * as examTurns from "../examTurns.js";
import type * as examiner from "../examiner.js";
import type * as exams from "../exams.js";
import type * as http from "../http.js";
import type * as httpBoundary_bearerToken from "../httpBoundary/bearerToken.js";
import type * as httpBoundary_completionRequest from "../httpBoundary/completionRequest.js";
import type * as httpBoundary_examMessageRequest from "../httpBoundary/examMessageRequest.js";
import type * as httpBoundary_jsonBody from "../httpBoundary/jsonBody.js";
import type * as httpBoundary_requestValidation from "../httpBoundary/requestValidation.js";
import type * as httpBoundary_responses from "../httpBoundary/responses.js";
import type * as httpBoundary_resultBody from "../httpBoundary/resultBody.js";
import type * as httpBoundary_routes from "../httpBoundary/routes.js";
import type * as httpBoundary_serviceAuth from "../httpBoundary/serviceAuth.js";
import type * as httpBoundary_submitRunRequest from "../httpBoundary/submitRunRequest.js";
import type * as httpBoundary_uploadUrlRequest from "../httpBoundary/uploadUrlRequest.js";
import type * as httpBoundary_workerEventRequest from "../httpBoundary/workerEventRequest.js";
import type * as httpBoundary_youtubeUrl from "../httpBoundary/youtubeUrl.js";
import type * as model_examLookup from "../model/examLookup.js";
import type * as model_examMessageView from "../model/examMessageView.js";
import type * as model_examValidators from "../model/examValidators.js";
import type * as model_examView from "../model/examView.js";
import type * as model_examVocabulary from "../model/examVocabulary.js";
import type * as model_proxyHealthNotices from "../model/proxyHealthNotices.js";
import type * as model_proxyHealthRecord from "../model/proxyHealthRecord.js";
import type * as model_proxyHealthVocabulary from "../model/proxyHealthVocabulary.js";
import type * as model_proxyRotation from "../model/proxyRotation.js";
import type * as model_runLifecycle from "../model/runLifecycle.js";
import type * as model_runLookup from "../model/runLookup.js";
import type * as model_runNotices from "../model/runNotices.js";
import type * as model_runQueue from "../model/runQueue.js";
import type * as model_runStatusView from "../model/runStatusView.js";
import type * as model_runValidators from "../model/runValidators.js";
import type * as model_runVocabulary from "../model/runVocabulary.js";
import type * as model_storedRunResult from "../model/storedRunResult.js";
import type * as model_workerAccess from "../model/workerAccess.js";
import type * as operatorChat_operatorChat from "../operatorChat/operatorChat.js";
import type * as operatorChat_operatorChatFactory from "../operatorChat/operatorChatFactory.js";
import type * as operatorChat_telegramOperatorChat from "../operatorChat/telegramOperatorChat.js";
import type * as operatorChat_telegramSendError from "../operatorChat/telegramSendError.js";
import type * as operatorNotices from "../operatorNotices.js";
import type * as provisioning from "../provisioning.js";
import type * as proxyHealth from "../proxyHealth.js";
import type * as proxyProbe from "../proxyProbe.js";
import type * as runs from "../runs.js";
import type * as sandbox_daytonaExaminerGateway from "../sandbox/daytonaExaminerGateway.js";
import type * as sandbox_daytonaGatewayFactory from "../sandbox/daytonaGatewayFactory.js";
import type * as sandbox_daytonaSandboxGateway from "../sandbox/daytonaSandboxGateway.js";
import type * as sandbox_examinerGateway from "../sandbox/examinerGateway.js";
import type * as sandbox_examinerGatewayFactory from "../sandbox/examinerGatewayFactory.js";
import type * as sandbox_examinerLaunch from "../sandbox/examinerLaunch.js";
import type * as sandbox_examinerTurnInput from "../sandbox/examinerTurnInput.js";
import type * as sandbox_examinerTurnOutput from "../sandbox/examinerTurnOutput.js";
import type * as sandbox_sandboxCommandTimeoutError from "../sandbox/sandboxCommandTimeoutError.js";
import type * as sandbox_sandboxGateway from "../sandbox/sandboxGateway.js";
import type * as sandbox_sandboxGatewayError from "../sandbox/sandboxGatewayError.js";
import type * as sandbox_sandboxNotFoundError from "../sandbox/sandboxNotFoundError.js";
import type * as sandbox_workerLaunch from "../sandbox/workerLaunch.js";
import type * as sandboxRuns from "../sandboxRuns.js";
import type * as security_runToken from "../security/runToken.js";
import type * as security_secretRedaction from "../security/secretRedaction.js";
import type * as security_sha256 from "../security/sha256.js";
import type * as watchPage_undiciWatchPageClient from "../watchPage/undiciWatchPageClient.js";
import type * as watchPage_watchPageClient from "../watchPage/watchPageClient.js";
import type * as watchPage_watchPageClientFactory from "../watchPage/watchPageClientFactory.js";
import type * as watchPage_watchPageProbe from "../watchPage/watchPageProbe.js";
import type * as watchdog from "../watchdog.js";
import type * as workerApi from "../workerApi.js";
import type * as workerRuns from "../workerRuns.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  clientApi: typeof clientApi;
  "config/env": typeof config_env;
  "config/maxParallelRuns": typeof config_maxParallelRuns;
  "config/proxyUrls": typeof config_proxyUrls;
  crons: typeof crons;
  dispatcher: typeof dispatcher;
  examApi: typeof examApi;
  examTurns: typeof examTurns;
  examiner: typeof examiner;
  exams: typeof exams;
  http: typeof http;
  "httpBoundary/bearerToken": typeof httpBoundary_bearerToken;
  "httpBoundary/completionRequest": typeof httpBoundary_completionRequest;
  "httpBoundary/examMessageRequest": typeof httpBoundary_examMessageRequest;
  "httpBoundary/jsonBody": typeof httpBoundary_jsonBody;
  "httpBoundary/requestValidation": typeof httpBoundary_requestValidation;
  "httpBoundary/responses": typeof httpBoundary_responses;
  "httpBoundary/resultBody": typeof httpBoundary_resultBody;
  "httpBoundary/routes": typeof httpBoundary_routes;
  "httpBoundary/serviceAuth": typeof httpBoundary_serviceAuth;
  "httpBoundary/submitRunRequest": typeof httpBoundary_submitRunRequest;
  "httpBoundary/uploadUrlRequest": typeof httpBoundary_uploadUrlRequest;
  "httpBoundary/workerEventRequest": typeof httpBoundary_workerEventRequest;
  "httpBoundary/youtubeUrl": typeof httpBoundary_youtubeUrl;
  "model/examLookup": typeof model_examLookup;
  "model/examMessageView": typeof model_examMessageView;
  "model/examValidators": typeof model_examValidators;
  "model/examView": typeof model_examView;
  "model/examVocabulary": typeof model_examVocabulary;
  "model/proxyHealthNotices": typeof model_proxyHealthNotices;
  "model/proxyHealthRecord": typeof model_proxyHealthRecord;
  "model/proxyHealthVocabulary": typeof model_proxyHealthVocabulary;
  "model/proxyRotation": typeof model_proxyRotation;
  "model/runLifecycle": typeof model_runLifecycle;
  "model/runLookup": typeof model_runLookup;
  "model/runNotices": typeof model_runNotices;
  "model/runQueue": typeof model_runQueue;
  "model/runStatusView": typeof model_runStatusView;
  "model/runValidators": typeof model_runValidators;
  "model/runVocabulary": typeof model_runVocabulary;
  "model/storedRunResult": typeof model_storedRunResult;
  "model/workerAccess": typeof model_workerAccess;
  "operatorChat/operatorChat": typeof operatorChat_operatorChat;
  "operatorChat/operatorChatFactory": typeof operatorChat_operatorChatFactory;
  "operatorChat/telegramOperatorChat": typeof operatorChat_telegramOperatorChat;
  "operatorChat/telegramSendError": typeof operatorChat_telegramSendError;
  operatorNotices: typeof operatorNotices;
  provisioning: typeof provisioning;
  proxyHealth: typeof proxyHealth;
  proxyProbe: typeof proxyProbe;
  runs: typeof runs;
  "sandbox/daytonaExaminerGateway": typeof sandbox_daytonaExaminerGateway;
  "sandbox/daytonaGatewayFactory": typeof sandbox_daytonaGatewayFactory;
  "sandbox/daytonaSandboxGateway": typeof sandbox_daytonaSandboxGateway;
  "sandbox/examinerGateway": typeof sandbox_examinerGateway;
  "sandbox/examinerGatewayFactory": typeof sandbox_examinerGatewayFactory;
  "sandbox/examinerLaunch": typeof sandbox_examinerLaunch;
  "sandbox/examinerTurnInput": typeof sandbox_examinerTurnInput;
  "sandbox/examinerTurnOutput": typeof sandbox_examinerTurnOutput;
  "sandbox/sandboxCommandTimeoutError": typeof sandbox_sandboxCommandTimeoutError;
  "sandbox/sandboxGateway": typeof sandbox_sandboxGateway;
  "sandbox/sandboxGatewayError": typeof sandbox_sandboxGatewayError;
  "sandbox/sandboxNotFoundError": typeof sandbox_sandboxNotFoundError;
  "sandbox/workerLaunch": typeof sandbox_workerLaunch;
  sandboxRuns: typeof sandboxRuns;
  "security/runToken": typeof security_runToken;
  "security/secretRedaction": typeof security_secretRedaction;
  "security/sha256": typeof security_sha256;
  "watchPage/undiciWatchPageClient": typeof watchPage_undiciWatchPageClient;
  "watchPage/watchPageClient": typeof watchPage_watchPageClient;
  "watchPage/watchPageClientFactory": typeof watchPage_watchPageClientFactory;
  "watchPage/watchPageProbe": typeof watchPage_watchPageProbe;
  watchdog: typeof watchdog;
  workerApi: typeof workerApi;
  workerRuns: typeof workerRuns;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};

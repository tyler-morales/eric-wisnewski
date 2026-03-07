import { onRequestDelete as __api_comments_js_onRequestDelete } from "/Users/tyler/Projects/Code/eric-wisnewski/functions/api/comments.js"
import { onRequestGet as __api_comments_js_onRequestGet } from "/Users/tyler/Projects/Code/eric-wisnewski/functions/api/comments.js"
import { onRequestPost as __api_comments_js_onRequestPost } from "/Users/tyler/Projects/Code/eric-wisnewski/functions/api/comments.js"
import { onRequestPut as __api_comments_js_onRequestPut } from "/Users/tyler/Projects/Code/eric-wisnewski/functions/api/comments.js"

export const routes = [
    {
      routePath: "/api/comments",
      mountPath: "/api",
      method: "DELETE",
      middlewares: [],
      modules: [__api_comments_js_onRequestDelete],
    },
  {
      routePath: "/api/comments",
      mountPath: "/api",
      method: "GET",
      middlewares: [],
      modules: [__api_comments_js_onRequestGet],
    },
  {
      routePath: "/api/comments",
      mountPath: "/api",
      method: "POST",
      middlewares: [],
      modules: [__api_comments_js_onRequestPost],
    },
  {
      routePath: "/api/comments",
      mountPath: "/api",
      method: "PUT",
      middlewares: [],
      modules: [__api_comments_js_onRequestPut],
    },
  ]
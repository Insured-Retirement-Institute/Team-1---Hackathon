import type { Todo } from "@/models/Todo";

export const test = () => fetch('/api/todos')
	.then(response => response.json() as Promise<Todo[]>)

export const awsTest = () => fetch('https://q4wbter4btlhos5jz2nm2u53ye0khura.lambda-url.us-east-1.on.aws/health')
	.then(res => res.json())

export async function fileToBase64(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader()
		reader.onload = () => {
			const result = reader.result as string
			// Remove the data URL prefix (e.g., "data:application/pdf;base64,")
			const base64 = result.split(',')[1] ?? ''
			resolve(base64)
		}
		reader.onerror = reject
		reader.readAsDataURL(file)
	})
}

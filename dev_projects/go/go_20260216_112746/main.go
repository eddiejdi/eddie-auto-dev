package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"

	// Create a new HTTP client
	client := &http.Client{}

	// Prepare the request body for creating an issue
	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "Test Issue",
			"description": "This is a test issue created by Go Agent."
		}
	}`)

	// Set the request headers
	req, err := http.NewRequest("POST", jiraURL, strings.NewReader(body))
	if err != nil {
		fmt.Println("Error creating request:", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

	// Send the request
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("Error sending request:", err)
		return
	}
	defer resp.Body.Close()

	// Read the response body
	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Error reading response body:", err)
		return
	}

	// Parse the JSON response
	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		fmt.Println("Error parsing JSON response:", err)
		return
	}

	// Print the created issue details
	fmt.Printf("Created Issue: %+v\n", issue)
}
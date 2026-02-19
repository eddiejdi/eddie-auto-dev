package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents the structure of a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

// createJiraIssue sends a POST request to create an issue in Jira
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	// Create a new HTTP client
	client := &http.Client{}

	// Prepare the request body for creating an issue
	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "%s"},
			"summary": "%s",
			"description": "%s"
		}
	}`, projectKey, summary, description)

	// Set the request headers
	req, err := http.NewRequest("POST", jiraURL, strings.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

	// Send the request
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	// Read the response body
	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("Error reading response body: %v", err)
	}

	// Parse the JSON response
	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		return nil, fmt.Errorf("Error parsing JSON response: %v", err)
	}

	return &issue, nil
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"

	// Test cases for createJiraIssue function

	// Case 1: Success with valid input
	testSuccess := func(projectKey, summary, description string) {
		issue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
		if err != nil {
			fmt.Printf("Test failed: %v\n", err)
			return
		}
		fmt.Printf("Created Issue: %+v\n", issue)
	}

	testSuccess("YOUR_PROJECT_KEY", "Test Issue", "This is a test issue created by Go Agent.")

	// Case 2: Error due to invalid input (empty summary)
	testInvalidInput := func(projectKey, summary, description string) {
		issue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
		if err == nil {
			fmt.Printf("Test failed: Expected error but got none\n")
			return
		}
		fmt.Println("Error:", err)
	}

	testInvalidInput("", "Test Issue", "This is a test issue created by Go Agent.")
}
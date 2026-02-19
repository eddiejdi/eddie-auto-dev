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

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
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
	testCase1, err := createJiraIssue(jiraURL, username, password, "YOUR_PROJECT_KEY", "Test Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		fmt.Println("Test case 1 failed:", err)
		return
	}
	fmt.Printf("Created Issue: %+v\n", testCase1)

	// Case 2: Error due to invalid project key
	testCase2, err := createJiraIssue(jiraURL, username, password, "INVALID_PROJECT_KEY", "Test Issue", "This is a test issue created by Go Agent.")
	if err == nil {
		fmt.Println("Test case 2 failed (expected error):")
		return
	}
	fmt.Printf("Error: %v\n", err)

	// Case 3: Error due to missing summary field
	testCase3, err := createJiraIssue(jiraURL, username, password, "YOUR_PROJECT_KEY", "", "This is a test issue created by Go Agent.")
	if err == nil {
		fmt.Println("Test case 3 failed (expected error):")
		return
	}
	fmt.Printf("Error: %v\n", err)
}
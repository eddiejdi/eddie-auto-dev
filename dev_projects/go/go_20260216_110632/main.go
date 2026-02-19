package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraClient representa a conexão com o Jira API
type JiraClient struct {
	URL    string
	Token  string
}

// GetIssue retrieves an issue from Jira by its key
func (jc *JiraClient) GetIssue(issueKey string) (*http.Response, error) {
	req, err := http.NewRequest("GET", fmt.Sprintf("%s/rest/api/2/issue/%s", jc.URL, issueKey), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+jc.Token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	return resp, nil
}

// LogIssue logs an issue to the console
func (jc *JiraClient) LogIssue(issueKey string) error {
	resp, err := jc.GetIssue(issueKey)
	if err != nil {
		return err
	}

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	fmt.Println("Issue Details:")
	fmt.Println(string(body))
	return nil
}

func main() {
	jc := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net",
		Token:  "your-jira-token",
	}

	err := jc.LogIssue("ABC-123")
	if err != nil {
		fmt.Println("Error logging issue:", err)
	}
}
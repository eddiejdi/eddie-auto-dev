package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// Jira API response struct
type JiraResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// GoAgent struct to represent the Go Agent
type GoAgent struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// JiraClient struct to interact with Jira API
type JiraClient struct {
	Host     string
	Username string
	Password string
}

// SendWebhook sends a webhook to Jira
func (c *JiraClient) SendWebhook(goAgent GoAgent) error {
	url := fmt.Sprintf("%s/rest/api/2/issue", c.Host)
	req, err := http.NewRequest("POST", url, json.NewEncoder(&goAgent).Encode())
	if err != nil {
		return err
	}
	req.SetBasicAuth(c.Username, c.Password)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	var jiraResponse JiraResponse
	err = json.Unmarshal(body, &jiraResponse)
	if err != nil {
		return err
	}

	fmt.Println("Jira response:", jiraResponse.Error, jiraResponse.Message)
	return nil
}

func main() {
	goAgent := GoAgent{Name: "Go Agent", Version: "1.0"}
	jiraClient := JiraClient{Host: "http://jira.example.com", Username: "admin", Password: "password"}

	err := jiraClient.SendWebhook(goAgent)
	if err != nil {
		fmt.Println("Error sending webhook:", err)
	}
}
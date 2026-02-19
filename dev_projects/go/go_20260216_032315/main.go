package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para interagir com a API do Jira
type JiraClient interface {
	CreateIssue(title, description string) error
	UpdateIssue(issueID int, title, description string) error
}

// GoAgent é a classe principal que representa o Go Agent
type GoAgent struct {
	jiraClient JiraClient
}

// NewGoAgent cria uma nova instância de GoAgent
func NewGoAgent(jiraClient JiraClient) *GoAgent {
	return &GoAgent{jiraClient}
}

// CreateIssue cria uma nova tarefa no Jira
func (g *GoAgent) CreateIssue(title, description string) error {
	return g.jiraClient.CreateIssue(title, description)
}

// UpdateIssue atualiza uma tarefa existente no Jira
func (g *GoAgent) UpdateIssue(issueID int, title, description string) error {
	return g.jiraClient.UpdateIssue(issueID, title, description)
}

// MonitorProcesso monitora o progresso de um processo
func (g *GoAgent) MonitorProcesso() {
	fmt.Println("Iniciando monitoramento do processo...")
	// Simulação de processamento
	for i := 0; i < 10; i++ {
		fmt.Printf("Progresso: %d%%\r", i*10)
		time.Sleep(1 * time.Second)
	}
	fmt.Println("\nProcesso concluído!")
}

func main() {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("Tarefa de exemplo", "Descrição da tarefa")
	if err != nil {
		log.Fatalf("Erro ao criar tarefa: %v", err)
	}

	err = goAgent.UpdateIssue(1, "Tarefa atualizada", "Nova descrição da tarefa")
	if err != nil {
		log.Fatalf("Erro ao atualizar tarefa: %v", err)
	}

	goAgent.MonitorProcesso()
}
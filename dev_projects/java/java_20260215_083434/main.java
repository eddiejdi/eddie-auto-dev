import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.select.SelectField;
import com.atlassian.jira.user.User;
import com.atlassian.jira.user.util.UserUtil;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;

public class JavaAgent {

    public static void main(String[] args) {
        try {
            // Configuração do Jira
            Jira jira = new Jira("http://localhost:8080", "admin", "password");

            // Criação de um novo projeto
            Project project = createProject(jira, "MyProject");
            System.out.println("Projeto criado: " + project.getKey());

            // Criação de uma nova tarefa
            Issue issue = createIssue(jira, project, "Task 1", "This is a test task.");
            System.out.println("Tarefa criada: " + issue.getKey());

            // Configuração do Java Agent para monitorar a tarefa
            configureJavaAgent(jira, issue);

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static Project createProject(Jira jira, String projectName) throws IOException {
        JiraServiceContext serviceContext = new JiraServiceContext("admin", "password");
        Project project = jira.createProject(serviceContext, projectName);
        return project;
    }

    private static Issue createIssue(Jira jira, Project project, String summary, String description) throws IOException {
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        SelectField statusField = customFieldManager.getSelectFieldByName("Status");
        TextField summaryField = fieldManager.getTextFieldByName("Summary");

        Issue issue = jira.createIssue(serviceContext, project.getKey(), "Task 1", description);
        issue.setFieldValue(summaryField, summary);
        issue.setFieldValue(statusField, "To Do");

        return issue;
    }

    private static void configureJavaAgent(Jira jira, Issue issue) throws IOException {
        // Simulação de configuração do Java Agent
        String agentUrl = "http://localhost:8081/agent";
        HttpClient client = HttpClient.newHttpClient();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(agentUrl))
                .POST(HttpRequest.BodyPublishers.ofString("issueKey=" + issue.getKey()))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("Configuração do Java Agent concluída: " + response.body());
    }
}
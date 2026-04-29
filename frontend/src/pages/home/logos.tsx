import serviceNowSvg from "../../assets/home/servicenow.svg";
import jiraSvg from "../../assets/home/jira.svg";

export const IntegrationLogo = ({ id }: { id: string }) => {
  if (id === "servicenow") return <img src={serviceNowSvg} alt="ServiceNow" className="w-full h-full" />;
  if (id === "jira") return <img src={jiraSvg} alt="Jira" className="w-full h-full" />;
  return null;
};
import { RequestDetailClient } from "./request-detail-client";

export default async function RequestDetailPage(props: PageProps<"/requests/[id]">) {
  const { id } = await props.params;
  return <RequestDetailClient id={id} />;
}

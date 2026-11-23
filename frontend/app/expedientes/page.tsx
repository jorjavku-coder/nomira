import { redirect } from "next/navigation";

/** La lista de expedientes vive en /app; /expedientes llevaba a «404». */
export default function Expedientes() {
  redirect("/app");
}
